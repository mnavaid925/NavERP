# Review — Sales 8.17 Workflow & Process Automation

**Changeset:** `15b30066...HEAD` (BASE saved at Phase 0; 44 commits at review start)
**Sub-module:** `8.17 Workflow & Process Automation` (Module 8 — Sales Management System, `sales`)
**Review date:** 2026-10-26
**Reviewers (run strictly one after another, all read-only):** code-reviewer → explorer → frontend-reviewer → performance-reviewer → qa-smoke-tester → security-reviewer

Findings are appended per reviewer as each reports, then deduped and sorted Critical → Important → Minor with IDs (`C1`, `I3`, `M7`) for the Phase 5 `code-fixer`.

---

## Reviewer 1 of 6 — `code-reviewer`

### Verdict
Commit after fixing Critical+Important — no Critical findings; five Important items (two share the same masked-`IntegrityError` root cause), the rest is polished, tenant-safe work that closely follows the frozen contract.

### Critical
None.

### Important

1. **GAP-09 confirmed — duplicate-tier ledger back-fill 500s with a misleading error.** `apps/sales/forms/WorkflowProcessAutomation/SalesApprovalDecisions.py:18` — `SalesApprovalDecisionForm` is the only 8.17 form not using `TenantUniqueMixin`, and its `clean()` (`:53-62`) validates shape but never the `(tenant, target_key, tier)` `UniqueConstraint`; `target_key` is `editable=False` and still `""` when `_post_clean()` runs, so `validate_unique()` cannot see it either. Submitting a second manual entry for the same target+tier passes `is_valid()`, then `obj.save()` at `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:137` raises `IntegrityError` → HTTP 500. Worse, `TenantNumbered.save()` at `apps/sales/models/_base.py:31-50` catches that `IntegrityError`, misattributes it to an auto-number collision, retries 5× and re-raises `"Could not allocate a unique SAD number … after 5 attempts"` (`_base.py:46-50`), masking the real cause.
   **Fix (minimal):** in `SalesApprovalDecisionForm.clean()`, after the exactly-one-target guard, compute the prospective key (`kind = "quote"/"order_hold"/"contract"; key = f"{kind}:{target.pk}"`) and `if SalesApprovalDecision.objects.filter(tenant=self.tenant, target_key=key, tier=tier).exists(): self.add_error("tier", "This target already has a recorded decision at that tier.")`.
   **Clone-family (§11): yes** — the retry loop that swallows non-number `IntegrityError`s is duplicated in at least `apps/{sales,accounting,crm,scm,inventory,hrm,procurement,projects,tenants}/models/_base.py` plus `apps/inventory/models/LotSerialTracking/LotNumberRules.py:142`; every `TenantNumbered` subclass with an extra unique constraint and no form-side uniqueness check inherits the same masked 500. Finding grep: `grep -rn "except IntegrityError" apps/*/models/_base.py`.

2. **Decide path can hit the same masked 500 on a "gapped" chain.** `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:246` — `tier = chain.filter(decision="approved").count() + 1` collides with an existing row when the chain has a tier gap (the manual ledger form happily records tier 1 and tier 3 of 3 with no tier 2): approved-count is 2 → tier 3 → `(tenant, target_key, 3)` already exists → `IntegrityError` → the same misleading retry-loop error. The detail view's `pending_tier` (`:91-97`) has the mirror bug — it derives pending-ness from counts, so a `{1,3}` chain shows "Pending — Tier 3" which already exists.
   **Fix:** `tier = (chain.aggregate(Max("tier"))["tier__max"] or 0) + 1` (deviates from the contract's "count + 1" pin — worth a contract note), and compute `pending_tier` as the lowest positive tier absent from `{row.tier for row in chain}`.

3. **Catch-all assignment rule with empty conditions cannot be created through the form.** `apps/sales/forms/WorkflowProcessAutomation/SalesAssignmentRules.py:44-48` — `clean_conditions()` reads `self.cleaned_data.get("is_catch_all")`, but Django cleans fields in `Meta.fields` order (`:24-29`) and `conditions` precedes `is_catch_all`, so the value is always `None` at that point; `validate_process_conditions([], None)` then rejects with "An empty rule must be explicitly marked as a catch-all." even with the checkbox ticked. The seeder creates exactly this row (`seed_sales.py` sar1: `is_catch_all=True`, no conditions) and the detail template renders a catch-all empty state, so this is a real supported shape.
   **Fix:** move the empty/catch-all interaction into the form's `clean()` (where both cleaned values exist), or pass the raw `self.data.get("is_catch_all")`.

4. **Seeded approval chain is a demo dead-end (smoke-tester's finding — a seeder defect, worth fixing).** `apps/sales/management/commands/seed_sales.py:4135` picks `CPQQuote.objects.filter(tenant=tenant).order_by("pk").first()` — that quote is seeded `approval_status="approved"` (`seed_sales.py:1129`) and owned by the tenant admin (`owner` at `seed_sales.py:189-190`; all quotes are `owner=owner`). The tier-2 chain recorded at `:4236-4248` therefore renders live approve/reject forms that are always rejected by the final-status guard (`views/…/SalesApprovalDecisions.py:229`) and the self-approval guard (`:232`).
   **Fix:** pick `CPQQuote.objects.filter(tenant=tenant).exclude(approval_status__in=["approved", "rejected"]).order_by("pk").first()` and, when `second_user` exists, set `quote.owner = second_user; quote.save(update_fields=["owner", "updated_at"])` before recording tier 1 (skip the chain when no eligible quote/user exists).

5. **Delete on the "immutable" decision register is unguarded.** `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:182-190` — any tenant admin can POST-delete any `SalesApprovalDecision`, including a signed tier that already flipped `CPQQuote.approval_status`, contradicting the view's own docstring ("an approved chain is not meant to be deletable") and the model's register-IS-the-history design; checklist §6 requires edit/delete on posted/approved records to be status-locked, and the detail sidebar (`templates/…/salesapprovaldecision/detail.html:229`) offers it unconditionally.
   **Fix:** in the view, refuse deletion when the chain has more than this one row or when the row is final-tier/quote-flipping (e.g. `if SalesApprovalDecision.objects.filter(tenant=tenant, target_key=obj.target_key).count() > 1: messages.error(...); return redirect(...)`), and hide the button under the same condition.

### Minor

1. **Admin base-class divergence — real but low-impact; the SPD admin is the part that actually matters.** `apps/sales/admin.py:1166/1175/1218` use plain `admin.ModelAdmin` while every 8.12–8.16 sibling uses `TenantScopedFKAdmin` (defined at `apps/sales/admin.py:873`). SAR/SAT hand-roll `formfield_for_foreignkey` that duplicates the base (maintainability drift only — behavior is equivalent, and the `territory` `is_active=True` narrowing genuinely cannot be expressed by the declarative base, so that claim checks out). But `SalesProcessDefinitionAdmin` (`admin.py:1166`) narrows **nothing**: `owner` and `job_definition` dropdowns are cross-tenant for any tenant-scoped staff user, with only `Model.clean()` as a backstop (and it no-ops when `tenant_id` is unset on the add form).
   **Fix:** base all four on `TenantScopedFKAdmin`, declare `tenant_user_fk_fields`/`tenant_fk_fields`, keep only the territory-`is_active` and M2M overrides.

2. **Templates offer admin-gated actions to non-admins.** None of the 12 new templates wraps create/edit/delete/run/approve/reject in `{% if request.user.is_superuser or request.user.is_tenant_admin %}`, yet every mutating view raises `PermissionDenied` (`apps/core/decorators.py:13-20`) — non-admins get a 403 dead-end. The 8.12/8.13 siblings gate correctly (e.g. `templates/sales/contactaccountmanagement/accountplan/list.html:17`). Examples: `templates/…/salesapprovaldecision/detail.html:163-235`, `templates/…/salesassignmentrule/list.html:122-136`, `templates/…/salesprocessdefinition/detail.html:186-201`.

3. **Action-form `tier_count` is trusted over the recorded chain snapshot.** `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:241-245` prefers the POSTed value (the "hidden" `NumberInput` at `detail.html:176/195` is tamperable), letting an admin silently extend a 2-tier chain to 9 mid-flight.
   **Fix:** when the chain already has rows, use `Max("tier_count")` and ignore the form value.

4. **Ledger form accepts `tier=0`.** `apps/sales/forms/WorkflowProcessAutomation/SalesApprovalDecisions.py:58-61` checks `tier > tier_count` only; `PositiveSmallIntegerField`'s form min is 0, and a tier-0 row breaks the count-based pending derivation.
   **Fix:** add `if tier is not None and tier < 1: self.add_error("tier", ...)`.

5. **Unused import.** `apps/sales/models/WorkflowProcessAutomation/SalesAssignmentRules.py:6` — `from apps.accounts.models import User` is never used (all user FKs go through `settings.AUTH_USER_MODEL`).

6. **Seeder dead variable + non-deliverable demo trigger.** `apps/sales/management/commands/seed_sales.py:4144` — `sat1` is assigned and never referenced; it is also `audience_kind="all"`, which `fire_alert_trigger` deliberately never delivers (`views/…/SalesAlertTriggers.py:47`), so the headline "Deal Inactivity Watcher" demo trigger cannot produce an alert row. Consider `audience_kind="user"` + `sat1.audience_users.add(owner)`.

7. **Seeder fallback rows bypass model invariants.** `apps/sales/management/commands/seed_sales.py:~4224-4231` — the no-territory fallback creates a `round_robin` SAR with zero `eligible_owners`, which `SalesAssignmentRule.clean()` (`models/…/SalesAssignmentRules.py:126-127`) would reject; `create()` never validates. Same for `territory_manager` rows if a territory ever lacks a manager (seeded CRM territories do have one — `seed_crm.py:331-334` — so only the fallback branch is live).

8. **Notify node fires even when nothing matched.** `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:204-215` — `fire_alert_trigger` runs regardless of `matched`, so a run over zero-matching records still consumes the trigger's cooldown window (`mark_fired`). This is contract-pinned (§3.1 step 5, `contract-sales-8.17.md:929`), so it is a design note, not drift — but gating on `if matched:` (or recording the choice in the gap file) would make "Run now" honest.

### Done well

The `target_key` single-choke-point design is exactly right: `compute_target_key()` is called only from `save()` (`models/…/SalesApprovalDecisions.py:134-136`), the seeder goes through `record()` (never `bulk_create`), and the decide view re-derives the same string (`views/…:217`) — no write path can persist `target_key=""` past the form's exactly-one-target guard. Also: explicit `_CHAIN_ORDER` on every chain read (L61 honored), `select_for_update()` + tenant-scoped 404 in the decide path, the bounded-JSON validators applied on both the model `clean()` and form `clean_*` paths, `mark_evaluated`/`mark_fired` correctly split so a suppressed fire never starts a cooldown, `SAT_TO_MDA_ALERT_TYPE` verified to cover all 7 SAT types with valid MDA values and matching urgency choices, migration 0031 matching the models with all names ≤30 chars, all re-exports present (including `fire_alert_trigger` deliberately exported from the sub-package only, per contract §3.5), and `LIVE_LINKS["8.17"]` verbatim against `NavERP.md:1428-1432`. Bullet 5 pointing at 8.3's `sales:party_enrichment_list` (route verified at `apps/sales/urls/ContactAccountManagement/PartyEnrichment.py:6`) is acceptable — staff-reachable, ownership-ruled inline, and the unbuilt merge half is gap-registered, so it is not an L32 dead offer.

### Suggested tests

- `apps/sales/tests/test_workflow_forms.py` — SAR form: catch-all + empty conditions passes `is_valid()` (regression for Important-3); SAD ledger form: duplicate `(target, tier)` yields a form error, not `IntegrityError` (Important-1); `tier=0` rejected; SPD/SAT JSON bounds (21 conditions, >16 KiB, NaN, non-scalar) rejected on the form path.
- `apps/sales/tests/test_workflow_views.py` — decide on a gapped chain does not 500 (Important-2); delete of a signed tier in a multi-row chain is refused (Important-5); cross-tenant pk → 404 on all four detail/edit/delete views; non-admin POST to run/approve/delete → 403; `fire_alert_trigger`: cooldown suppression leaves `last_fired_at` untouched, role-audience rows are tenant-scoped, `fire_count` increments only on delivery; Run-now bounds at `MAX_RUN_RECORDS`.
- Seeder test: after `seed_sales`, `admin_acme` can POST-approve tier 2 of the seeded chain and the quote flips to `approved` (Important-4).

### Routing

- **performance-reviewer:** Run-now materializes up to 100 full target rows and evaluates JSON conditions in Python (`views/…/SalesProcessDefinitions.py:196-202`) with per-node trigger queries; `fire_alert_trigger` creates up to 50 `MobileDealAlert` rows one `create()` per row (`views/…/SalesAlertTriggers.py:49-59`) — note `MobileDealAlert` is `TenantNumbered`, so `bulk_create` would skip number minting; assess whether that loop needs a bound or batching. SAD detail runs a second unbounded chain query (fine in practice, chains are ≤9).
- **security-reviewer:** the decide action form's hidden-but-tamperable fields (`target_kind`/`target_id`/`tier_count` re-read from POST at `views/…/SalesApprovalDecisions.py:203-213,241-245`) — tenant re-check under `select_for_update()` looks IDOR-safe, please confirm; plus the unguarded register delete (Important-5) and the missing template-level admin gating (Minor-2).
- **frontend-reviewer:** `salesapprovaldecision/detail.html:169-206` renders the same `action_form` widgets in both the approve and reject forms → duplicate DOM ids (`id_comment`, `id_tier_count`, …) and label collisions; `tier_count` is a visible `NumberInput` stuffed in a `class="hidden"` div rather than a `HiddenInput`; Run-now button shows for non-active processes that the view will refuse.

---

## Reviewer 2 of 6 — `explorer`

### Verdict

The 8.17 changeset lines up with the rest of the repo: every url name, view, template path, re-export, FK target, `related_name`, context key, badge class and migration field cross-checked clean — the only contract drift found is one place where the **contract is wrong and the code is right** (`as_db_int` on a raw JSON int).

### Critical

None.

### Important

None beyond code-reviewer's I1–I5 (not duplicated here).

### Minor

1. **`LIVE_LINKS` comment overstates the as-built registry wiring.** `apps/core/navigation.py:2623` — the comment claims SPD "registers into `core.WorkflowDefinition` (0.11 registry)", but no *runtime* code registers SPD (or any 8.17 model) there; only the **seeder** creates one registry row (`apps/sales/management/commands/seed_sales.py`, step 5). So the registration is demo-tenant-only, not a product behaviour.
   **Fix:** reword the comment to say the registry row is seeded per demo tenant, or record the missing runtime registration in `.agents/tasks/gaps-sales-8.17.md`.

2. **Contract §3.1 pins a shape that would 500 — record the deviation so Phase 5 does not "restore" it.** `.claude/tasks/contract-sales-8.17.md` §3.1 step 5 (`:929`) pins `as_db_int(node["params"].get("alert_trigger_id"))`, passing the **raw JSON int**. `as_db_int` does `(value or "").strip()` (`apps/core/crud.py:67`) and ints have no `.strip()` → `AttributeError`. The seeder itself writes an int (`"alert_trigger_id": sat2.pk`). The code's `str(...)` wrap (`apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:208-210`) is correct.
   **Fix:** add it as deviation 13 in contract §10 — this is contract-wrong / code-right, not drift to be corrected.

3. **Admin read-only precedent confirmed consistent.** `SalesApprovalDecisionAdmin` (`apps/sales/admin.py`) mirrors the `PartyEnrichmentEventAdmin` precedent at `apps/sales/admin.py:184-196` exactly, including `has_add/change/delete = False`. The only admin issue is the base-class divergence already recorded as code-reviewer Minor-1.

### Contract-vs-code drift (all verified, none requiring a code change)

| Contract spot | Code | Ruling |
|---|---|---|
| §3.1 `:929` — `as_db_int(<raw int>)` | `str(...)` wrap at `views/…/SalesProcessDefinitions.py:208-210` | **Contract wrong, code right** → record as deviation 13 (Minor 2 above) |
| §2.3 — `clean()` pins `tier > tier_count` unconditionally | guarded `if tier_count and tier and …` at `forms/…/SalesApprovalDecisions.py:60` | Benign defensive widening; same spot as code-reviewer I1/M4 |
| §3.3 — chain query relies on `Meta.ordering` | explicit `.order_by(*_CHAIN_ORDER)` | Improvement, L61-consistent, no action |

Everything else in contract §2 / §3 / §4 / §5 matches the code verbatim.

### Routing to remaining reviewers

- **test-writer / Phase 6:** `apps/sales/tests/test_ordermanagement_numbering.py:166-183` inspects `seed_sales.Command._seed_tenant` source text and asserts exactly 2 occurrences of `.order_by("pk").first()`. The 8.17 seeder work is a **sibling method**, so the count is untouched (verified by reading), but it is the one existing test the seeder edit could theoretically break — worth a full unfiltered suite run before Phase 6 closes.
- **frontend-reviewer:** confirms independently that the duplicate DOM ids in the two decide forms at `templates/sales/workflowprocessautomation/salesapprovaldecision/detail.html:169-206` are present.

### Confirmed correct (evidence gathered, no action needed)

- All **23** url names match contract §4.1–§4.5; all **25** distinct `{% url %}` names across the 12 templates resolve; all **12** `render()` paths exist on disk.
- Re-exports complete at **both** levels — views `apps/sales/views/__init__.py:462-486` + `__all__` `:534-537`; forms `:141-148` + `:208-210`; models `:166-177`; plus all four new sub-package `__init__.py` files.
- All four list views pass exactly the five pinned context keys (list var + `page_obj` + choice sets + filter querysets).
- Every L10-risky nullable-FK `get_full_name|default:username` sits inside an `{% if fk %}` guard.
- All **18** `sales_wpa_*` `related_name`s are unique repo-wide; every FK target grep-verified to exist.
- **No duplicate engine** — the 0.11 registry is *reused* via `WorkflowDefinition.objects.get_or_create` in the seeder, not re-implemented (L55 satisfied).
- Literal routes precede `<int:pk>` in each entity url module and in the concatenated `apps/sales/urls/__init__.py`; the four new route prefixes (`processes/`, `assignment-rules/`, `approval-decisions/`, `alert-triggers/`) appear nowhere else in the app.
- Migration `0031` is field-by-field identical to the models and **purely additive** (4 × `CreateModel`, no `AlterField`/`RemoveField`).
- Zero relative imports inside the new packages.
- Templates use **only colour-named badge classes**; all six exist at `static/css/theme.css:286-291`, and `text-danger` exists at `:403` (L33 clean). Zero unclosed `{#`. Every POST form carries `{% csrf_token %}`.
- Seeder is idempotent, and its `handle()` literal summary was updated to include 8.15/8.16/8.17.

---

## Reviewer 3 of 6 — `frontend-reviewer`

**Scope reviewed:** all 12 templates under `templates/sales/workflowprocessautomation/` against `15b30066...HEAD`, plus views/forms/models read for context only.

**Independently verified clean:** every `{#` closes same-line and the one multi-line note correctly uses `{% comment %}` (`salesapprovaldecision/detail.html:149-154`) — L2 clean; all badge classes are colour-named and exist in `static/css/theme.css` (`badge-slate/info/green/amber/red/muted`), all branch values match the exact model CHOICES (`SEVERITY_CHOICES` low/normal/high/urgent, `STATUS_CHOICES` draft/active/paused/archived) with `get_*_display` `{% else %}` fallbacks — L33 clean; every POST form carries `{% csrf_token %}`; all tables sit in `.table-wrap`; the pk filter uses `|stringformat:"d"` (`salesassignmentrule/list.html:67`) and re-selects from `request.GET`; pagination goes through the L9-safe shared `partials/pagination.html` which preserves all GET params; nullable-FK displays are `{% if %}`-guarded (L10 clean); no `dark:` variants, which matches sibling convention (0 in `accountplan/list.html`).

### Critical

None.

### Important

**I-F1. Duplicate DOM ids and unassociated labels on the sub-module's primary action UI.** `templates/sales/workflowprocessautomation/salesapprovaldecision/detail.html:169-206` renders the *same* `action_form` twice. `{{ action_form.target_kind }}`, `.target_id`, `.approval_kind`, `.tier_count` render at `:172-177` (approve form) **and** `:191-196` (reject form); `{{ action_form.comment }}` renders at `:180` **and** `:199` → duplicate `id_target_kind`, `id_target_id`, `id_approval_kind`, `id_tier_count`, `id_comment` (invalid HTML; `getElementById`, label-click and `:invalid` targeting all hit the first twin). The `<label class="form-label text-xs">Comment</label>` at `:179` and `:198` has **no `for` attribute at all** — an a11y blocker on the core approve/reject action. Additionally `tier_count` is a visible `NumberInput` (`apps/sales/forms/WorkflowProcessAutomation/SalesApprovalDecisions.py:96-97`) stuffed in a `class="hidden"` div rather than a true hidden input (this is the markup half of code-reviewer Minor-3; the tamperability half stays server-side).
*(Confirms code-reviewer's routing and explorer's independent confirmation; quantified here — 5 id pairs, not 2.)*
**Fix (template-only; keeps the prefix-less POST keys the decide view binds at `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:202`):** replace the widget renders in both forms with hand-written inputs — `<input type="hidden" name="target_kind" value="…">` style for the four carry fields (unique or omitted `id`s), `tier_count` as `<input type="hidden" name="tier_count" value="{{ tier_count }}">`, and the comment as `<textarea name="comment" id="approve_comment" class="form-input">` / `id="reject_comment"` with matching `<label for="approve_comment">` / `<label for="reject_comment">`. A two-prefixed-form view change would also work but requires the decide view to detect the prefix — heavier.

**I-F2. "Run now" advertises an action that can never succeed.** `templates/sales/workflowprocessautomation/salesprocessdefinition/detail.html:190-196` renders the run form unconditionally, but `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:192-194` redirects with `messages.error("Only an active process definition can run.")` whenever `status != "active"`. For draft/paused/archived processes the page offers a guaranteed-fail button (compounded by code-reviewer Minor-2: non-admins additionally get 403 on it).
**Fix:** wrap the run form in `{% if process_definition.status == 'active' %}…{% endif %}`, optionally with an `{% else %}` hint ("Activate this process to run it").

### Minor

**M-F1. Missing admin gating — confirmed, not re-derived** (= code-reviewer Minor-2). Grep for `is_superuser`/`is_tenant_admin` across the 12 new templates returns **0 hits**, while the correct sibling pattern is `{% if request.user.is_superuser or request.user.is_tenant_admin %}` around mutating affordances (`templates/sales/contactaccountmanagement/accountplan/list.html:17`). Apply to the four list pages' "New …" buttons + edit/delete actions and the four detail sidebars' Edit/Delete/Run/Sign blocks.

**M-F2. Empty rows don't use the `.empty-state` component.** `salesprocessdefinition/list.html:139`, `salesassignmentrule/list.html:141`, `salesapprovaldecision/list.html:141`, `salesalerttrigger/list.html:151` render a bare centered `<td>`. Sibling convention: `<td colspan="N"><div class="empty-state"><i data-lucide="…"></i><h3>No …</h3><p>…</p></div></td>` (`accountplan/list.html:17`; `.empty-state` exists in theme.css). Cosmetic consistency.

**M-F3. Draft badge colour — ruled repo-consistent, no change needed.** `salesprocessdefinition/list.html:101` badges Draft as `badge-slate` while the persona's canonical map says draft→info; however the sibling (`accountplan/list.html:17`) also uses `badge-slate` for draft. Recorded only so the dedupe pass does not re-raise it.

### Verdict

**ship-after-fixes** — no Critical; I-F1 (duplicate ids/labels on the core approve/reject UI) and I-F2 (dead-end Run button) must land in Phase 5; the rest is polish.

### Praised

The list pages' filter bars are exemplary — every select restores its `request.GET` state, the territory pk compare uses `|stringformat:"d"` per the filter rules, and pagination reuses the L9-safe shared partial with full param preservation. The `{% comment %}` block at `salesapprovaldecision/detail.html:149-154` even documents *why* it isn't in brace-hash form.

---

## Reviewer 4 of 6 — `performance-reviewer`

**Scope:** `git diff 15b30066...HEAD` — the four 8.17 model/view/form/url modules, migration `0031`, the new seeder method (`apps/sales/management/commands/seed_sales.py:4125-4255`), and the 12 templates (query-in-loop check only).

### Corrections to reviewer 1's routing

- **SAD detail "second unbounded chain read": CORRECTED.** `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:83-97` performs **one** chain read (`list(...)`) and derives `rejected_exists`, `approved_count`, `tier_count`, `pending_tier` in Python from the materialized list — the optimal shape for a ≤9-row chain, no change. The three-queries-over-one-chain problem is in the **decide** path (`:222`, `:243`, `:246`), not the detail view.
- **`bulk_create` in `fire_alert_trigger`: RULED OUT — and not for the stated reason alone.** `MobileDealAlert` carries `UniqueConstraint(fields=["tenant","number"], name="sales_mda_ten_num_uniq")` (`apps/sales/models/MobileSales/MobileDealAlerts.py:90-97`). `bulk_create()` bypasses `TenantNumbered.save()` (`apps/sales/models/_base.py:31-51`), so `number` stays `""` — row 1 inserts, **row 2 raises `IntegrityError`**. It is a hard failure, not a silent blank. A "mint a block, then `bulk_create`" variant is not race-safe without a lock, and hardening `next_number` is explicitly an app-wide follow-up (`apps/core/utils.py:66-68`). **Keep per-row `.create()`.**

### Critical

None.

### Important

**P-I1. Run-now: FK-named conditions cost `1 + 100×F` queries.** `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:196-202` materializes ≤100 rows (correct `[:100]` LIMIT shape), then `_evaluate_condition` does `getattr(record, field, None)` (`:43`). `validate_process_conditions` **deliberately dropped the field whitelist** (`apps/sales/models/WorkflowProcessAutomation/SalesProcessDefinitions.py:56-58`: "field may be any non-empty str ≤255"), so an admin can legitimately save `{"field":"customer","operator":"contains","value":"Acme"}`. Every FK-named condition then lazily fetches the relation **per record**: `CPQQuote` has 12 FKs, `Opportunity` 10, `SalesOrder` 8 — worst realistic case (20 conditions over ~6 distinct FKs) is **1 + ~600 queries** for one POST. `str(actual)` on an FK value also invokes `__str__`, a further hop for `SalesOrder.__str__` (`self.customer.name`, `apps/scm/models/OrderManagement/SalesOrders.py:181-183`) and `CustomerSubscription.__str__` (`self.account.name`) — L18 chained, though both bottom out at a scalar.
**Fix** (semantics unchanged, `1 + 1` query): derive the join paths from the JSON before slicing —
`fk = {f.name for f in model._meta.get_fields() if f.many_to_one}`; `paths = [c["field"] for c in obj.conditions if c.get("field") in fk]`; `model.objects.filter(tenant=tenant).select_related(*paths).order_by("pk")[:MAX_RUN_RECORDS]`.
**Explicitly rule out a blanket `.only()`/`.defer()`** here: because the matched field set is data-driven, any statically-deferred field that a condition names becomes a `DeferredAttribute` reload — **1 extra query per record per field**, strictly worse. Deferral is only safe *after* the referenced-field set is known (then defer heavy text/JSON columns absent from it — `CPQQuote` has 5, `Case` 3). `MAX_RUN_RECORDS = 100` itself is fine; the row count is not the cost.

**P-I2. Run-now has no per-*run* alert budget — up to ~2100 queries and 1000 INSERTs in one transaction.** The node loop (`:204-215`) iterates up to `MAX_PROCESS_NODES = 20` notify nodes, each calling `fire_alert_trigger`, which creates up to `MAX_ALERT_RECIPIENTS = 50` rows at 2 queries each (`next_number` SELECT + INSERT) ≈ **105 queries per fire**. 20 distinct triggers → **~2100 queries / 1000 `MobileDealAlert` rows in a single POST**, all inside `@transaction.atomic`. The cooldown is the only dedupe and it fails when `cooldown_hours = 0` — a legal value (`apps/sales/models/WorkflowProcessAutomation/SalesAlertTriggers.py:88`, `PositiveSmallIntegerField(default=24)`, exposed at `apps/sales/forms/WorkflowProcessAutomation/SalesAlertTriggers.py:28`): `is_on_cooldown` (`:101-105`) then evaluates `last_fired_at > now` → False → the same trigger refires per node.
**Fix:** dedupe by trigger id and cap the run — `seen = set(); fired = 0` … `if trigger_id in seen: continue` … `if fired >= MAX_ALERTS_PER_RUN: break` … `fired += len(fire_alert_trigger(...))` with `MAX_ALERTS_PER_RUN = 50`. Also pass one shared `now=timezone.now()` into every fire so cooldown is evaluated consistently within a run.

**P-I3. SAD has no `(tenant, number)` index or uniqueness — every ledger INSERT does an unindexed sort.** `next_number()` (`apps/core/utils.py:86-90`) runs `filter(tenant, number__startswith="SAD-").order_by("-number").first()` on **every** insert; its own comment says that shape is chosen because "it is satisfiable by the `(tenant, <field>)` index". Migration `apps/sales/migrations/0031_…py:75-79` gives `SalesApprovalDecision` only `(tenant, decision)` and `(tenant, target_key, tier)` — no `(tenant, number)` — so each insert scans the tenant's range and top-N sorts. SAD is the append-only register that grows fastest (one row per tier per target, forever), and the 8.17 write paths insert into it constantly (`record()`, the ledger form, the decide view). **Second consequence:** with no uniqueness, `TenantNumbered.save()`'s 5× retry loop (`apps/sales/models/_base.py:32-50`) **can never trigger** on a number collision — a concurrent double-mint silently persists two `SAD-00007` rows.
**App-wide framing:** this matches an existing *minority* gap, not the convention — **49 of 63** `TenantNumbered` models in `apps/sales` declare it, including 8.16's `MobileDealAlert`, `CustomerContract`, `CustomerSubscription`, `AccountPlan`, `CommissionPlan`; the 10 that lack it are 8.4/8.5/8.7-era tables. Migration `sales/0010` added exactly these indexes for CPQQuote/Bundle/QuoteApprovalRule for this reason. So fixing the other 10 is an app-wide pass, but **SAD should get it in 8.17 — it is the ledger.**
**Fix:** `models.UniqueConstraint(fields=["tenant","number"], name="sales_sad_tnt_num_uniq")` (a unique constraint supplies the index; matches `sales_mda_ten_num_uniq`). **This is schema-affecting → Phase 5 must generate a new migration (next number `0032`; re-verify at generation time).** `SPD`/`SAR`/`SAT` are small config tables — Minor there, safe to fold into the app-wide pass.

### Minor

1. **Decide path: 3 queries over one ≤9-row chain.** `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:222` (`.exists()`), `:243` (`aggregate(Max)`), `:246` (`.count()`) each hit the same `(tenant, target_key)` chain. Collapse to one: `chain.aggregate(has_rejected=Count("id", filter=Q(decision="rejected")), approved=Count("id", filter=Q(decision="approved")), max_tiers=Max("tier_count"))`. Saves 2 queries per approve/reject POST. (Code-reviewer's Important-2 fix changes `:246` to `Max("tier")` — fold both into the same aggregate.)
2. **Fire path writes the same row twice.** `fire_alert_trigger` calls `mark_evaluated` (`views/…/SalesAlertTriggers.py:34` → 1 UPDATE) and then, when it delivers, `mark_fired` (`:61`), which **already writes `last_evaluated_at`** (`models/…/SalesAlertTriggers.py:111-116`). 2 UPDATEs where 1 suffices → 2N for a future scheduler over N triggers (GAP-sales-8.17-01). **Fix:** evaluate cooldown in Python first and call `mark_evaluated` only on the suppressed branch (or have `mark_fired` subsume it).
3. **`select_related` over-fetch on the list pages.** `views/…/SalesApprovalDecisions.py:37-39` joins `quote` + `order_hold` + `contract` (three wide tables) but the list template renders only `target_key`/`record_label` (`templates/…/salesapprovaldecision/list.html:96-98`) — 3 wasted LEFT JOINs on the ledger's hottest page; same at `:76-79` in the detail view, which fetches `target_object` separately at `:104`. Also `views/…/SalesAssignmentRules.py:28-30` (`default_owner`, `territory` unused), `views/…/SalesProcessDefinitions.py:77` (`owner` unused), `views/…/SalesAlertTriggers.py:72-74` (both unused). Not N+1 — sub-millisecond on 15-row pages except the SAD one. **Fix:** drop the unrendered paths.
4. **SAR detail misses the chained join (L18).** `templates/…/salesassignmentrule/detail.html:67-68` renders `assignment_rule.territory.manager.get_full_name`; `views/…/SalesAssignmentRules.py:69-71` selects `territory` only → **1 extra query** per detail page. **Fix:** `select_related(..., "territory__manager")`.
5. **Checked, not a finding:** all four list views apply every filter *before* `paginate(request, qs, 15)` (correct LIMIT/OFFSET + SQL COUNT via `apps/core/crud.py:22-34`); `evaluated = len(records)` on an already-materialized list is free (`:199`); `.exists()`/`.count()`/`.aggregate()` are used correctly everywhere; **zero** related-manager access (`.all`/`.count`/`.exists`/`.first`) in any of the 12 templates; the SAD chain read is fully served by the `(tenant, target_key, tier)` unique index plus the pinned `_CHAIN_ORDER`; every FK column gets Django's automatic index; the seeder has no per-row loops and correctly refuses `bulk_create` for SAD (`target_key` must be computed in `save()`). The `Meta.ordering = ["priority","name","id"]` filesort on SPD/SAR/SAT list pages has no `(tenant, priority)` index, but those are tens-of-rows config tables and the pattern is app-wide — not worth a fork.

### Suggested tests for Phase 6 (`django_assert_max_num_queries`)

- **SAD/SPD/SAR/SAT list:** same bound at 1 row and at 15 rows — proves no N+1 and catches a regressed `select_related`. Suggest `django_assert_max_num_queries(8)` (count + page + auth/session); the test-writer should pin the observed constant.
- **Run-now with a FK-named condition** (e.g. `{"field":"customer","operator":"contains","value":"Acme"}` on `target_entity="order"`) over 20 seeded `SalesOrder`s: assert a bound **independent of row count** (`max_num_queries(15)`), which fails today at ~21 and passes after P-I1.
- **Run-now alert budget:** 3 notify nodes → 3 distinct triggers, `cooldown_hours=0`, 10 recipients each → assert `MobileDealAlert.objects.count() <= MAX_ALERTS_PER_RUN` and `max_num_queries` bounded (P-I2).
- **`fire_alert_trigger` with 50 recipients:** assert every created row has a distinct non-empty `number` — the regression guard that keeps a future "optimization" from swapping in `bulk_create` (see the ruling above).
- **Decide path:** `max_num_queries` bound on `sales_approval_decision_approve` (drops by 2 after Minor-1).

### Verdict

**ship-after-fixes** — no Critical; P-I1 (data-driven `select_related` on Run-now, and *not* `.only()`), P-I2 (per-run alert budget + trigger dedupe) and P-I3 (`(tenant, number)` on the SAD ledger, **plus its migration**) should land in Phase 5; the Minors are polish.

---

## Reviewer 5 of 6 — `qa-smoke-tester` — CARRIED FORWARD from Phase 3.5, fresh re-run mandated after Phase 5

**Judgment call, stated transparently.** The `qa-smoke-tester` gate already ran as Phase 3.5 and returned **132/132 PASS with zero app-code fixes required**. Nothing has changed since: `git log 15b30066..HEAD` shows the last runtime-touching commit is `25577a02` (`seed_sales.py`), and every commit after it (`8cc6afde`) is documentation. The working tree contains only this untracked review file. Reviewers 1–4 were read-only. Re-running the identical sweep now would reproduce the identical result and burn a DB cycle for no new coverage — so the Phase 3.5 evidence is recorded here as this reviewer's Phase 4 pass.

**This is NOT a waiver.** Phase 5's `code-fixer` will change runtime code (P-I1/P-I2/P-I3 touch views, models and a new migration; I-F1/I-F2 touch templates; code-reviewer I1–I5 touch forms, views and the seeder). A **fresh full `qa-smoke-tester` sweep is mandatory after Phase 5 lands**, before Phase 6 closes, and its result must be appended to this file as a second `Reviewer 5` entry. If Phase 5 somehow changes no runtime code, the carry-forward stands.

### Phase 3.5 evidence (as run)

- **All 16 GET pages** (4 entities × list/detail/create-form/edit-form) rendered **200** as `admin_acme` / `password`, each with content assertions, not just status: expected page title present, a seeded record's identifier present, **0** `{#` leaks, **0** `{% comment` leaks (L2/L3/L8).
- **All 3 POST actions** exercised: `sales_process_definition_run`, `sales_approval_decision_approve`, `sales_approval_decision_reject` — each **200/302**, no 500.
- **18 filter cases** across the four list pages (`?q=`, `?status=`, `?target_entity=`, `?trigger_event=`, `?assignment_mode=`, `?is_active=`, `?territory=`, `?approval_kind=`, `?decision=`, `?target_kind=`, `?alert_type=`, `?severity=`, `?audience_kind=`) — all applied, all re-selecting in the widget.
- **13 junk-param cases** (`?territory=abc`, `?status=<script>`, `?page=-1`, …) — **no 500s** (L11 clean).
- **Pagination:** `?page=2` and `?page=999` both safe — L9 guards hold via the shared `partials/pagination.html`.
- **Cross-tenant IDOR:** every detail/edit/delete URL requested with a `globex`-tenant pk while logged in as `admin_acme` → **404** on all four entities.
- **Sidebar:** `LIVE_LINKS["8.17"]` renders **5 Live bullets**, all resolving (L32 clean — the bullet-5 pointer at `sales:party_enrichment_list` is a real staff page).
- **Design system:** **0** badge-name violations across the 12 templates (L33 clean — independently re-confirmed by reviewers 2 and 3).
- **Seeder idempotency:** `seed_sales` run twice → identical counts both runs: `SalesProcessDefinition=34`, `SalesAssignmentRule=34`, `SalesApprovalDecision=17`, `SalesAlertTrigger=34`, `core.WorkflowDefinition=33`.
- **DB hygiene:** the probe script deleted its own rows **by explicit primary key**; zero residue left in the shared `nav_erp` database (verified independently after the run). No bulk `delete()` on any shared table.
- `manage.py check` → **0 issues**; `makemigrations --check --dry-run` → "No changes detected" (state as of Phase 3.5; P-I3 will legitimately change this in Phase 5).

---

## Reviewer 6 of 6 — `security-reviewer`

### S1 · High · `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:241-247, 276-280`

**Tampered `tier_count` shortens a multi-tier chain and flips a quote to `approved` with one signature.** *Upgrades code-reviewer Minor-3, which only described the lengthening direction (2→9); the escalation is the opposite one.* Exploit: a chain holds a recorded row `tier=1, tier_count=3, decision=approved`; a tenant admin who does **not** own the quote POSTs `sales:sales_approval_decision_approve` with `tier_count=2` → `tier = approved_count+1 = 2`, `2 > 2` is false, and `:276` `tier >= tier_count` → `2 >= 2` → `approval_status="approved"`, one tier early. The `Max("tier_count")` fallback at `:243` is dead code whenever the field is submitted — and it always is (rendered `NumberInput`). The row also *stores* the tampered `tier_count`, so the register reads "2 of 2": the audit history is falsified, not just bypassed.

```python
recorded = chain.aggregate(Max("tier_count"))["tier_count__max"]
tier_count = recorded or form.cleaned_data.get("tier_count") or 1   # DB wins, never the POST
```

Better: drop `tier_count` from `SalesApprovalDecisionActionForm` entirely — a security decision must not read a request field.

### S2 · High · `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:182-190` (+ `templates/sales/workflowprocessautomation/salesapprovaldecision/detail.html:229`)

**Confirms reviewer 1 Important-5; new exploit path: deleting a *rejection* silently resurrects a rejected hold/contract.** The only rejection guard is `chain.filter(decision="rejected").exists()` (`:222`). Quotes are protected incidentally — `:281-285` also writes `approval_status="rejected"`, which `:229` then blocks — but **`OrderHold` and `CustomerContract` get no status write** (contract deviation 10), so the SAD row is the *sole* record of the rejection. POST-delete it → chain re-opens → approve at tier 1 → a rejected hold/contract is approved with no trace. `write_audit_log` snapshots only `str(obj)` = `"SAD-00007 · quote:12 tier 2/3 approved"` (`apps/core/utils.py:46-49` + `models/…/SalesApprovalDecisions.py:175-176`); approver, comment and `requested_by` are unrecoverable. The edit path (`views/…:155-166`, fields `comment`/`due_at`) additionally lets the same admin rewrite a signed tier's justification.

```python
if SalesApprovalDecision.objects.filter(tenant=tenant, target_key=obj.target_key).count() > 1 \
        or obj.decision == "rejected" or obj.is_final_tier:
    messages.error(request, "Recorded decisions are immutable — the register is the audit trail.")
    return redirect("sales:sales_approval_decision_detail", pk=obj.pk)
```

### S3 · Medium · `apps/sales/models/WorkflowProcessAutomation/SalesApprovalDecisions.py:47,54,61` → `apps/sales/views/QuoteProposalCPQ/CPQQuotes.py:246-247`, `apps/sales/views/OrderManagement/OrderHolds.py:507-519`

**The new `PROTECT` FKs 500 three sibling delete views, two of which persist a false audit row.** Ordinary flow: sign/reject a quote in 8.17, then POST `sales:cpq_quote_delete` (allowed while `status in ["draft","rejected"]` — a *different* field from `approval_status`) → unhandled `ProtectedError` → 500. Neither view catches it, unlike the four sales sites that already do (`OpportunityOutcomes.py:225`, `ForecastSubmissions.py:527`, `ForecastPeriods.py:432`, `CompetitiveIntelligence.py:229`). Worse: both write the `AuditLog` **before** `delete()` with **no `@transaction.atomic`**, so the immutable log keeps a row asserting a deletion that never happened (`CustomerContracts.py:163-176` is atomic → 500 only).

```python
try:
    quote.delete()
except ProtectedError:
    messages.error(request, f"Quote {number} has approval decisions recorded — it cannot be deleted.")
    return redirect("sales:cpq_quote_detail", pk=quote.pk)
write_audit_log(request.user, quote, "delete", {...}, tenant=tenant)   # audit AFTER success
```

**Family grep:** `grep -rn "on_delete=models.PROTECT" apps/*/models/` cross-checked against delete views lacking `except ProtectedError`.

### S4 · Low (ruling on the routed design point) · `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:43`

**No RCE, no dunder escape, no cross-tenant disclosure — but `getattr` executes property getters and sits outside the `try`.** `getattr` binds methods without calling them (`==`/`str()` on a bound method is inert); access is single-level with no dot chaining, and only the `matched` integer is returned, so no value ever reaches a template. Residual: any `@property` on the 7 target models *runs*, once per record ×100, and `except TypeError` begins at `:44` — one getter raising a non-`AttributeError` (Decimal/date arithmetic, DB error) 500s Run-now; `str(actual)` on a property returning a QuerySet evaluates it. Today's getters are benign (verified `CPQQuote.is_editable/is_approved/is_expired/can_convert` null-guarded) → latent, not exploitable. The allowlist closes this class *and* perf P-I1:

```python
safe = {f.name for f in model._meta.get_fields() if f.concrete and not f.is_relation}
if not all(c["field"] in safe for c in obj.conditions):
    messages.error(request, "Conditions must reference stored fields only."); return redirect(...)
```

### S5 · Low · `apps/sales/forms/WorkflowProcessAutomation/SalesApprovalDecisions.py:35-51`

**Ledger form permits forged attribution.** `approver`/`requested_by` accept any tenant user, with no `approver != quote.owner` guard and no provenance marker — one admin can back-fill tiers 1-2 of 3 as the finance director and VP, then sign tier 3 via the decide view (`3 >= 3` → quote `approved`), producing a register that shows a complete three-signature chain that never happened. `record()` and form rows are indistinguishable. **Interim fix:** drop `approver` from `Meta.fields`, set `obj.approver = request.user` in `sales_approval_decision_create`. **Proper:** add a `source` field (`manual`/`decide`/`system`, default `manual`) in the migration Phase 5 already needs for P-I3, badge it in the chain view, and refuse the `approval_status` flip when any chain row is `manual`.

### Confirmations (no new content)

- **Routed item 1 — IDOR: CONFIRMED SAFE.** `target_kind` is `ChoiceField(choices=TARGET_KIND_CHOICES)` (`forms/…/SalesApprovalDecisions.py:89`) so `SAD_TARGET_MODELS[kind]` cannot KeyError; `views/…:212-214` is `get_object_or_404(<Model>.objects.select_for_update(), pk=target_id, tenant=tenant)` → a foreign pk 404s. The ledger form is equally safe: `TenantModelForm.__init__` (`apps/core/forms/_common.py:51-55`) auto-scopes every `ModelChoiceField`, and `forms/…:44-51` re-scopes all seven FKs. **No cross-tenant read or write anywhere in the four entities.** (The `tier_count` half of item 1 is refuted — see S1.)
- **Routed item 3 — view gate AIRTIGHT, so reviewer 1 Minor-2 stays Minor.** All **15** mutating views (not 11) carry `@tenant_admin_required`: SPD create/edit/delete/run (`views/…/SalesProcessDefinitions.py:119/145/173/187`), SAR create/edit/delete (`…/SalesAssignmentRules.py:82/108/135`), SAD create/edit/delete/approve/reject (`…/SalesApprovalDecisions.py:127/153/180/307/315`), SAT create/edit/delete (`…/SalesAlertTriggers.py:125/151/178`); all 7 POST-only actions also carry `@require_POST`; the 8 read views carry `@login_required`. Missing template gating is a cosmetic 403 dead-end, not an authz hole.
- **Templates — CSRF/XSS/L26 clean.** All 10 POST forms carry `{% csrf_token %}`; zero `|safe`, `mark_safe`, `autoescape off`, inline `style=`, `<script>`; the only inline handlers are static `onsubmit="return confirm('…')"` with no interpolated data.
- **Mass assignment (L22/L28) clean:** `version`, `cursor`, `last_assigned_owner/_at`, `fire_count`, `last_fired_at`, `last_evaluated_at`, `target_key`, `decided_at` all excluded from `Meta.fields`. L20/L25 (no secret fields), SQLi (no `.raw()`/`.extra()`/`cursor.execute`), open redirect (no `?next=`) all n/a.
- **Hand to `qa-smoke-tester`** for runtime confirmation (this reviewer is read-only): **S1** (POST `tier_count=2` on a `tier_count=3` chain flips the quote) and **S3** (delete a quote that has an SAD row → 500 + a surviving AuditLog row).

### Prioritized summary

1. **High — S1** tampered `tier_count` → single-signature approval of a multi-tier quote + falsified register.
2. **High — S2** unguarded register delete → erased rejection resurrects a rejected hold/contract (confirms reviewer 1 Important-5).
3. **Medium — S3** new `PROTECT` FKs 500 three sibling delete views; two persist a false audit row.
4. **Low — S4** unwhitelisted `getattr` executes property getters outside the `try` (latent 500; no RCE/IDOR/disclosure).
5. **Low — S5** ledger form allows forged approver attribution and a synthetic full chain.

### Verdict

**ship-after-fixes** — no Critical and no cross-tenant exposure, but S1 and S2 are separation-of-duties / audit-integrity breaks on the approval authority surface and must land in Phase 5 alongside S3.

---

## Consolidated findings register — deduped, sorted, ID-assigned (for the Phase 5 `code-fixer`)

All six reviewers have reported. **Zero Critical findings.** Every ID below is unique; the `code-fixer` works in ID order (all Important, then all Minor), one commit per file, marking each `[x] fixed` / `[~] skipped — reason` against this register.

Severity mapping used: `code-reviewer` Important → **Important**; `security-reviewer` High → **Important**; `security-reviewer` Medium reachable in ordinary use → **Important**; `performance-reviewer` Important → **Important**; `frontend-reviewer` Important → **Important**; everything else (incl. security Low) → **Minor**.

### Critical

**None.** No reviewer found a cross-tenant read or write, a CSRF/XSS hole, a mass-assignment leak, a secret exposure, or a page that 500s on the seeded happy path. `security-reviewer` verified all **15** mutating views carry `@tenant_admin_required` and all 7 POST-only actions also carry `@require_POST`; `qa-smoke-tester` verified cross-tenant pk → **404** on all four entities.

### Important (12) — all must land in Phase 5

- [ ] **I1 — Tampered `tier_count` shortens an approval chain and flips a quote to `approved` with one signature.** `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:241-247, 276-280`. *(security S1, High — **upgrades and supersedes** code-reviewer Minor-3, which only described the lengthening direction.)* The `Max("tier_count")` fallback at `:243` is dead code whenever the field is submitted, and it always is (rendered `NumberInput`). The tampered value is also *stored*, so the register itself reads "2 of 2" — the audit history is falsified, not merely bypassed.
  **Fix:** the DB always wins — `recorded = chain.aggregate(Max("tier_count"))["tier_count__max"]; tier_count = recorded or form.cleaned_data.get("tier_count") or 1`. Better still, drop `tier_count` from `SalesApprovalDecisionActionForm` entirely; a security decision must not read a request field. Fold in perf Minor-1's single-aggregate collapse at the same time (same lines).

- [ ] **I2 — Unguarded delete (and comment edit) on the immutable approval register; deleting a *rejection* resurrects a rejected hold/contract.** `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:182-190` and `:155-166`; button offered unconditionally at `templates/sales/workflowprocessautomation/salesapprovaldecision/detail.html:229`. *(code-reviewer Important-5 **merged with** security S2, High — same location, same root cause; security added the exploit path.)* Quotes are protected incidentally by the `:229` rejection guard because `:281-285` also writes `approval_status="rejected"`, but **`OrderHold` and `CustomerContract` get no status write** (contract deviation 10), so the SAD row is the *sole* record of their rejection. `write_audit_log` snapshots only `str(obj)`, so approver/comment/`requested_by` are unrecoverable after deletion.
  **Fix:** refuse the delete (and the comment edit) when the chain has >1 row, or the row is a rejection, or it is the final tier; hide both buttons in the template under the identical condition (L32 — do not offer what the view will refuse).

- [ ] **I3 — Duplicate manual ledger entry passes `is_valid()` then 500s, and the error message lies about the cause.** `apps/sales/forms/WorkflowProcessAutomation/SalesApprovalDecisions.py:18, 53-62` + `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:137`. *(code-reviewer Important-1; = GAP-sales-8.17-09.)* `SalesApprovalDecisionForm` is the only 8.17 form not using `TenantUniqueMixin`; `target_key` is `editable=False` and still `""` at `_post_clean()`, so the `(tenant, target_key, tier)` constraint is never form-validated. The raised `IntegrityError` is then caught by `TenantNumbered.save()` (`apps/sales/models/_base.py:31-50`), misattributed to a number collision, retried 5× and re-raised as `"Could not allocate a unique SAD number … after 5 attempts"`.
  **Fix:** compute the prospective `target_key` in the form's `clean()` and `add_error("tier", …)`. **Pattern-clone family — the same masking retry loop exists in `apps/{sales,accounting,crm,scm,inventory,hrm,procurement,projects,tenants}/models/_base.py` plus `apps/inventory/models/LotSerialTracking/LotNumberRules.py:142`;** grep `grep -rn "except IntegrityError" apps/*/models/_base.py`. Fix the 8.17 site only; record the family as an app-wide gap.

- [ ] **I4 — Gapped chain 500s the decide path.** `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:246` (`tier = chain.filter(decision="approved").count() + 1`) with the mirror bug in `pending_tier` at `:91-97`. *(code-reviewer Important-2.)* The ledger form allows tiers 1 and 3 of 3 with no tier 2, so the count-derived next tier collides with an existing row → `UniqueConstraint` → `IntegrityError` → 500.
  **Fix:** `tier = (chain.aggregate(Max("tier"))["tier__max"] or 0) + 1`; `pending_tier` = the lowest positive tier absent from `{row.tier for row in chain}`. Combine with I1's aggregate collapse and perf Minor-1 into **one** `chain.aggregate(...)` call.

- [ ] **I5 — A catch-all assignment rule cannot be created through the UI.** `apps/sales/forms/WorkflowProcessAutomation/SalesAssignmentRules.py:44-48` with `Meta.fields` at `:24-29`. *(code-reviewer Important-3.)* `clean_conditions()` reads `self.cleaned_data.get("is_catch_all")`, but Django cleans in `Meta.fields` order and `conditions` precedes `is_catch_all`, so it is always `None`; `validate_process_conditions([], None)` then rejects with "An empty rule must be explicitly marked as a catch-all." **even when the box is ticked.** The seeder creates exactly this row, so the UI cannot reproduce seeded data.
  **Fix:** move the interaction into the form's `clean()` (where both values are available), or read `self.data.get("is_catch_all")`.

- [ ] **I6 — The seeded approval chain is a demo dead-end.** `apps/sales/management/commands/seed_sales.py:4135` (quote pick), `:4236-4248` (tier-2 chain), against the guards at `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:229` (final-status) and `:232` (self-approval). *(code-reviewer Important-4.)* The chosen `CPQQuote` is seeded `approval_status="approved"` (`seed_sales.py:1129`) and owned by the tenant admin (`:189-190`), so the live approve/reject forms the page renders are **always** rejected by both guards — a reviewer/demo user can never exercise the sub-module's headline action.
  **Fix:** `.exclude(approval_status__in=["approved","rejected"])` on the quote pick, and reassign `quote.owner = second_user` before recording tier 1. Keep the seeder idempotent and the `--flush` order consistent.

- [ ] **I7 — The new `PROTECT` FKs 500 three sibling delete views, two of which persist a false audit row.** `apps/sales/models/WorkflowProcessAutomation/SalesApprovalDecisions.py:47,54,61` → `apps/sales/views/QuoteProposalCPQ/CPQQuotes.py:246-247`, `apps/sales/views/OrderManagement/OrderHolds.py:507-519`, `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:163-176`. *(security S3, Medium.)* Ordinary flow: sign or reject a quote in 8.17, then POST `sales:cpq_quote_delete` (permitted while `status in ["draft","rejected"]` — a *different* field from `approval_status`) → unhandled `ProtectedError` → 500. The first two write the `AuditLog` **before** `delete()` with no `@transaction.atomic`, so the immutable log keeps a row asserting a deletion that never happened.
  **Fix:** wrap each `delete()` in `try/except ProtectedError` → `messages.error(...)` + redirect to the detail page, and move `write_audit_log` **after** the successful delete (or inside `transaction.atomic()`). Four sales views already do this correctly — copy `OpportunityOutcomes.py:225`. **Family grep:** `grep -rn "on_delete=models.PROTECT" apps/*/models/` cross-checked against delete views lacking `except ProtectedError`.

- [ ] **I8 — Run-now issues `1 + 100×F` queries whenever a condition names an FK.** `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:196-202` + `_evaluate_condition` at `:43`. *(performance P-I1.)* `validate_process_conditions` deliberately allows `field` to be any non-empty string ≤255 (`apps/sales/models/WorkflowProcessAutomation/SalesProcessDefinitions.py:56-58`), so an FK-named condition lazily fetches the relation per record — `CPQQuote` has 12 FKs, `Opportunity` 10, `SalesOrder` 8; worst realistic case ≈ **1 + 600 queries** for one POST. `str(actual)` also invokes `__str__`, a further L18 hop for `SalesOrder` and `CustomerSubscription`.
  **Fix:** derive the join paths from the JSON *before* slicing — `paths = [c["field"] for c in obj.conditions if c.get("field") in fk]` then `.select_related(*paths)`. **Explicitly rule out a blanket `.only()`/`.defer()`** — with a data-driven field set, any statically-deferred field a condition names becomes a `DeferredAttribute` reload, strictly worse. **This same allowlist also closes Minor M14 (security S4)**: restrict to `{f.name for f in model._meta.get_fields() if f.concrete and not f.is_relation}` and reject conditions naming anything else, which stops `getattr` running arbitrary `@property` getters outside the `try`.

- [ ] **I9 — Run-now has no per-run alert budget: up to ~2100 queries and 1000 INSERTs in one transaction.** `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:204-215` → `apps/sales/views/WorkflowProcessAutomation/SalesAlertTriggers.py:49-59`. *(performance P-I2.)* 20 notify nodes × 50 recipients × 2 queries each. The cooldown is the only dedupe and it fails when `cooldown_hours = 0` — a legal, form-exposed value (`models/…/SalesAlertTriggers.py:88`, `forms/…/SalesAlertTriggers.py:28`) — so the same trigger refires per node.
  **Fix:** dedupe by trigger id (`seen` set), add `MAX_ALERTS_PER_RUN = 50` and break on it, and pass one shared `now=timezone.now()` into every fire so cooldown is evaluated consistently within a run. **Do NOT switch to `bulk_create`** — `MobileDealAlert` has `UniqueConstraint(["tenant","number"])` and `bulk_create` bypasses `TenantNumbered.save()`'s number minting, so row 2 raises `IntegrityError` (hard failure, not a silent blank).

- [ ] **I10 — `SalesApprovalDecision` has no `(tenant, number)` index or uniqueness, so every ledger INSERT does an unindexed top-N sort and the numbering retry loop can never fire.** `apps/sales/migrations/0031_salesalerttrigger_salesapprovaldecision_and_more.py:75-79`. *(performance P-I3.)* `next_number()` (`apps/core/utils.py:86-90`) runs `filter(tenant, number__startswith="SAD-").order_by("-number").first()` on every insert and its own comment says that shape assumes a `(tenant, <field>)` index. SAD is the fastest-growing append-only register in the sub-module. Second consequence: with no uniqueness, a concurrent double-mint silently persists two `SAD-00007` rows because `TenantNumbered.save()`'s retry (`apps/sales/models/_base.py:32-50`) never triggers.
  **Fix:** add `models.UniqueConstraint(fields=["tenant","number"], name="sales_sad_tnt_num_uniq")` (28 chars ≤ 30, L65; a unique constraint supplies the index and matches `sales_mda_ten_num_uniq`). **This is schema-affecting → generate a NEW migration.** 49 of 63 `TenantNumbered` models in `apps/sales` already declare it; the 10 that lack it are 8.4/8.5/8.7-era tables — record those as an app-wide gap rather than fixing them here. `SPD`/`SAR`/`SAT` are small config tables → Minor, fold into the app-wide pass.

- [ ] **I11 — The approve and reject forms render the same `action_form` twice: 5 pairs of duplicate DOM ids and labels with no `for` attribute.** `templates/sales/workflowprocessautomation/salesapprovaldecision/detail.html:169-206` (widgets at `:172-177` and `:191-196`; comment at `:180` and `:199`; bare `<label>` at `:179` and `:198`). *(frontend I-F1, confirming code-reviewer's routing and explorer's independent confirmation.)* Duplicate `id_target_kind`/`id_target_id`/`id_approval_kind`/`id_tier_count`/`id_comment` is invalid HTML — `getElementById`, label-click and `:invalid` targeting all hit the first twin — and the primary approve/reject action of the sub-module has an unassociated label (a11y blocker).
  **Fix (template-only; preserves the prefix-less POST keys the decide view binds at `views/…/SalesApprovalDecisions.py:202`):** hand-write the four carry fields as `<input type="hidden" name="…" value="…">` with unique or omitted `id`s, `tier_count` as a true `<input type="hidden">`, and the comment as `<textarea name="comment" id="approve_comment">` / `id="reject_comment"` with matching `<label for=…>`. Coordinate with I1 — if `tier_count` leaves the action form, this input disappears entirely.

- [ ] **I12 — "Run now" is offered for processes the view will always refuse.** `templates/sales/workflowprocessautomation/salesprocessdefinition/detail.html:190-196` vs `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:192-194`. *(frontend I-F2.)* Any draft/paused/archived definition renders a button that can only produce `messages.error("Only an active process definition can run.")` — a guaranteed-fail affordance (L32), compounded by Minor M2 for non-admins.
  **Fix:** wrap the run form in `{% if process_definition.status == 'active' %}…{% endif %}`, optionally with an `{% else %}` hint ("Activate this process to run it").

### Minor (16)

- [ ] **M1 — Django admin FK/M2M dropdowns are cross-tenant.** `apps/sales/admin.py:1166` (`SalesProcessDefinitionAdmin` narrows **nothing**, so `owner`/`job_definition` are unscoped) — base all four new ModelAdmins on `TenantScopedFKAdmin` (`apps/sales/admin.py:873`, the house base for 8.12–8.16). *(code-reviewer Minor-1; the contract's "TenantScopedAdmin" name does not exist — explorer-confirmed.)*
- [ ] **M2 — Templates offer admin-gated actions to non-admins.** None of the 12 templates contains `is_superuser`/`is_tenant_admin` (grep: 0 hits) while all 15 mutating views raise `PermissionDenied` (`apps/core/decorators.py:13-20`). *(code-reviewer Minor-2, confirmed by frontend M-F1 and explorer; **security verified the view gate is airtight, so this stays Minor** — a cosmetic 403 dead-end, not an authz hole.)* Correct sibling pattern: `templates/sales/contactaccountmanagement/accountplan/list.html:17`. Apply to the four list pages' "New …" buttons + edit/delete actions and the four detail sidebars.
- [ ] **M3 — The ledger form accepts `tier=0`.** `apps/sales/forms/WorkflowProcessAutomation/SalesApprovalDecisions.py:58-61` checks only `tier > tier_count`; `PositiveSmallIntegerField`'s form min is 0 and a tier-0 row breaks the count-based pending derivation. **Fix:** `if tier is not None and tier < 1: self.add_error("tier", …)`.
- [ ] **M4 — Unused import.** `apps/sales/models/WorkflowProcessAutomation/SalesAssignmentRules.py:6` — `from apps.accounts.models import User` (all user FKs go through `settings.AUTH_USER_MODEL`).
- [ ] **M5 — Seeder dead variable + non-deliverable headline demo trigger.** `apps/sales/management/commands/seed_sales.py:4144` — `sat1` is assigned and never referenced, and is `audience_kind="all"`, which `fire_alert_trigger` deliberately never delivers (`views/…/SalesAlertTriggers.py:47`), so the "Deal Inactivity Watcher" demo can never produce an alert row. **Fix:** `audience_kind="user"` + `sat1.audience_users.add(owner)`, and assert on `sat1` so it is not dead.
- [ ] **M6 — Seeder fallback rows bypass model invariants.** `apps/sales/management/commands/seed_sales.py:~4224-4231` — the no-territory fallback creates a `round_robin` SAR with zero `eligible_owners`, which `SalesAssignmentRule.clean()` (`models/…/SalesAssignmentRules.py:126-127`) would reject; `create()` never validates. **Fix:** give the fallback rule a pool, or make it `fixed_owner`.
- [ ] **M7 — Notify node fires even when nothing matched.** `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:204-215` — `fire_alert_trigger` runs regardless of `matched`, so a run over zero-matching records still consumes the trigger's cooldown window (`mark_fired`). Contract-pinned at §3.1 `:929`, so a design note rather than drift. **Fix:** gate on `if matched:` (or record the choice in the gap file).
- [ ] **M8 — `LIVE_LINKS` comment overstates the as-built registry wiring.** `apps/core/navigation.py:2623` claims SPD "registers into `core.WorkflowDefinition` (0.11 registry)", but only the **seeder** creates one registry row (`seed_sales.py` step 5) — no runtime code registers SPD. **Fix:** reword to say the registry row is seeded per demo tenant, or record the missing runtime registration in the gap file.
- [ ] **M9 — Contract §3.1 pins a shape that would 500; record the deviation so Phase 5 does not "restore" it.** `.claude/tasks/contract-sales-8.17.md:929` pins `as_db_int(node["params"].get("alert_trigger_id"))` on a **raw JSON int**; `as_db_int` does `(value or "").strip()` (`apps/core/crud.py:67`) and ints have no `.strip()`. The seeder writes an int and the code's `str(...)` wrap (`views/…/SalesProcessDefinitions.py:208-210`) is correct. **Fix (docs only):** add it as deviation 13 in contract §10 — contract-wrong / code-right.
- [ ] **M10 — Empty list rows don't use the `.empty-state` component.** `salesprocessdefinition/list.html:139`, `salesassignmentrule/list.html:141`, `salesapprovaldecision/list.html:141`, `salesalerttrigger/list.html:151` render a bare centered `<td>`. Sibling convention: `<td colspan="N"><div class="empty-state">…</div></td>` (`accountplan/list.html:17`).
- [ ] **M11 — Decide path issues 3 queries over one ≤9-row chain.** `apps/sales/views/WorkflowProcessAutomation/SalesApprovalDecisions.py:222` (`.exists()`), `:243` (`aggregate(Max)`), `:246` (`.count()`). **Fix:** collapse into one `chain.aggregate(has_rejected=Count("id", filter=Q(decision="rejected")), approved=Count("id", filter=Q(decision="approved")), max_tier=Max("tier"), max_tiers=Max("tier_count"))`. **Do this in the same edit as I1 and I4** — all three touch these lines.
- [ ] **M12 — Fire path writes the same row twice.** `views/…/SalesAlertTriggers.py:34` (`mark_evaluated`, 1 UPDATE) then `:61` (`mark_fired`), which already writes `last_evaluated_at` (`models/…/SalesAlertTriggers.py:111-116`). **Fix:** evaluate cooldown in Python first and call `mark_evaluated` only on the suppressed branch. Matters for the deferred scheduler (GAP-sales-8.17-01).
- [ ] **M13 — `select_related` over-fetch on the list pages.** `views/…/SalesApprovalDecisions.py:37-39` joins `quote`+`order_hold`+`contract` (three wide tables) but the list template renders only `target_key`/`record_label` (`salesapprovaldecision/list.html:96-98`) — 3 wasted LEFT JOINs on the ledger's hottest page; same at `:76-79` in the detail view. Also `views/…/SalesAssignmentRules.py:28-30`, `views/…/SalesProcessDefinitions.py:77`, `views/…/SalesAlertTriggers.py:72-74`. **Fix:** drop the unrendered paths.
- [ ] **M14 — SAR detail misses the chained join (L18).** `templates/…/salesassignmentrule/detail.html:67-68` renders `assignment_rule.territory.manager.get_full_name`; `views/…/SalesAssignmentRules.py:69-71` selects `territory` only → 1 extra query. **Fix:** `select_related(..., "territory__manager")`.
- [ ] **M15 — Unwhitelisted `getattr` runs property getters outside the `try`.** `apps/sales/views/WorkflowProcessAutomation/SalesProcessDefinitions.py:43` — `except TypeError` begins at `:44`, so a getter raising a non-`AttributeError` 500s Run-now, and `str(actual)` on a property returning a QuerySet evaluates it. *(security S4, Low — **no RCE, no dunder escape, no cross-tenant disclosure**; today's getters are benign and null-guarded, so latent.)* **Closed by I8's allowlist** — no separate edit needed; verify it is.
- [ ] **M16 — Ledger form permits forged approver attribution.** `apps/sales/forms/WorkflowProcessAutomation/SalesApprovalDecisions.py:35-51` — `approver`/`requested_by` accept any tenant user with no `approver != quote.owner` guard and no provenance marker, so one admin can back-fill tiers 1-2 of 3 as other people and then sign tier 3, producing a register showing a three-signature chain that never happened. `record()` and form rows are indistinguishable. *(security S5, Low.)* **Interim fix:** drop `approver` from `Meta.fields` and set `obj.approver = request.user` in the create view. **Proper fix:** add a `source` field (`manual`/`decide`/`system`) — batch it into the **same migration as I10** — badge it in the chain table, and refuse the `approval_status` flip when any chain row is `manual`.

### Ruled, no action (recorded so the dedupe is not re-litigated)

- **Draft badge colour.** `salesprocessdefinition/list.html:101` uses `badge-slate` for Draft where the frontend persona's canonical map says draft→info — but the sibling `accountplan/list.html:17` also uses `badge-slate`. **Ruled repo-consistent.** *(frontend M-F3.)*
- **`SalesApprovalDecisionAdmin` read-only shape** mirrors the `PartyEnrichmentEventAdmin` precedent at `apps/sales/admin.py:184-196` exactly, including `has_add/change/delete = False`. **Consistent.** *(explorer Minor-3.)*
- **Contract §2.3 / §3.3 drift.** `clean()` guards `tier > tier_count` with `if tier_count and tier and …` (`forms/…/SalesApprovalDecisions.py:60`) — benign defensive widening; the chain query adds explicit `.order_by(*_CHAIN_ORDER)` where the contract relied on `Meta.ordering` — an L61 improvement. **Both no-action.** *(explorer.)*
- **`bulk_create` for `MobileDealAlert`.** **Ruled out** — see I9. *(performance.)*
- **Blanket `.only()`/`.defer()` on Run-now.** **Ruled out** — see I8. *(performance.)*
- **SAD detail "second unbounded chain read".** **Does not exist** — `views/…/SalesApprovalDecisions.py:83-97` reads the chain once. *(performance correcting code-reviewer.)*

### Cross-cutting instructions for the `code-fixer`

1. **One migration, not two.** I10 (`(tenant, number)` unique constraint) and the proper M16 fix (`source` field) both need schema — generate a **single** new migration. Next number is `0032`; **re-verify against `apps/sales/migrations/` at generation time** (L43/L51/L53 — another session may be building in this checkout).
2. **One edit for the chain arithmetic.** I1, I4 and M11 all touch `views/…/SalesApprovalDecisions.py:222-247`. Do them as a single coherent rewrite of that block into one `chain.aggregate(...)`, then verify.
3. **One allowlist for Run-now.** I8 and M15 are the same change (`views/…/SalesProcessDefinitions.py:196-202` + `:43`).
4. **Keep the contract authoritative where it is right, and update it where it is wrong.** Only M9 is contract-wrong/code-right; do not "restore" the contract shape there.
5. **Surgical `Edit` only on shared files** (`seed_sales.py`, `admin.py`, `navigation.py`, contract `.md`) — never a full rewrite (L43/L59).
6. **One file per commit**, explicit paths, PowerShell-safe messages. Never `git add -A`. Never `git push`.
7. **Runtime confirmation owed to `qa-smoke-tester`** (its post-Phase-5 re-run is already mandated): S1/I1 (POST `tier_count=2` on a `tier_count=3` chain must NOT flip the quote) and S3/I7 (deleting a quote that has an SAD row must give a friendly error, not a 500, and must not leave a false AuditLog row).

### Suggested tests handed to Phase 6

**Naming (explorer-corrected — house convention, NOT code-reviewer's `test_workflow_*` names):** `apps/sales/tests/test_workflowprocessautomation_{models,forms,views,security}.py`, functions `test_workflowprocessautomation_*`, module-level helpers `_workflowprocessautomation_*`. `apps/sales/tests/` already has 15 subslugs and none is named `workflow*`. `conftest.py` (220 fixtures) is owned by Phase 6 step 1 alone.

- **Forms:** SAR catch-all + empty conditions passes `is_valid()` (I5); SAD duplicate `(target, tier)` yields a form error, not `IntegrityError` (I3); `tier=0` rejected (M3); SPD/SAT JSON bounds (21 conditions, >16 KiB, NaN, non-scalar) rejected on the form path.
- **Views:** decide on a gapped chain does not 500 (I4); delete of a signed/rejected/final tier is refused (I2); cross-tenant pk → 404 on all four detail/edit/delete; non-admin POST to run/approve/delete → 403; `fire_alert_trigger` cooldown suppression leaves `last_fired_at` untouched, role-audience rows are tenant-scoped, `fire_count` increments only on delivery; Run-now bounds at `MAX_RUN_RECORDS`.
- **Security:** tampered `tier_count` on a 3-tier chain does NOT flip `CPQQuote.approval_status` (I1); forged `approver` is not accepted from the ledger form (M16, if the interim fix lands).
- **Seeder:** after `seed_sales`, `admin_acme` can POST-approve tier 2 of the seeded chain and the quote flips to `approved` (I6); seeded counts stable across two runs.
- **Performance (`django_assert_max_num_queries`):** each of the four list views — same bound at 1 row and at 15 rows (suggest `max_num_queries(8)`; pin the observed constant); Run-now with an FK-named condition over 20 seeded `SalesOrder`s bounded **independently of row count** (`max_num_queries(15)` — fails today at ~21, passes after I8); Run-now alert budget with 3 nodes / `cooldown_hours=0` / 10 recipients each → `MobileDealAlert.objects.count() <= MAX_ALERTS_PER_RUN` (I9); `fire_alert_trigger` with 50 recipients → every row has a distinct non-empty `number` (the guard that keeps a future "optimization" from swapping in `bulk_create`); `sales_approval_decision_approve` bound drops by 2 after M11.
- **Regression watch:** `apps/sales/tests/test_ordermanagement_numbering.py:166-183` inspects `seed_sales.Command._seed_tenant` **source text** and asserts exactly 2 occurrences of `.order_by("pk").first()`. The 8.17 seeder work is a sibling method so the count is untouched (explorer verified by reading), but it is the one existing test the seeder edits (I6/M5/M6) could break — the full unfiltered run in Phase 6 step 3 is the gate (L47).

### Verdicts

| Reviewer | Verdict |
|---|---|
| 1 `code-reviewer` | Commit after fixing Critical+Important — no Critical, 5 Important |
| 2 `explorer` | Changeset lines up with the repo; only contract drift found is contract-wrong / code-right |
| 3 `frontend-reviewer` | **ship-after-fixes** |
| 4 `performance-reviewer` | **ship-after-fixes** |
| 5 `qa-smoke-tester` | **132/132 PASS** (Phase 3.5 carry-forward; fresh re-run mandated after Phase 5) |
| 6 `security-reviewer` | **ship-after-fixes** — no Critical, no cross-tenant exposure |

**Consolidated: 0 Critical · 12 Important · 16 Minor.** Proceed to Phase 5 (`code-fixer`).

