# Review findings — inventory 5.11 Stocktaking & Cycle Counting

Range: `094635e2...HEAD` · Generated: 2026-08-23
Wave (parallel): code-reviewer · explorer · frontend-reviewer · performance-reviewer · qa-smoke-tester · security-reviewer

## Summary

| Severity | Count |
|---|---|
| Critical | 1 |
| Important | 8 |
| Minor | 8 |
| **Total (deduped)** | **17** |

| Agent | Raw findings |
|---|---|
| security-reviewer | 4 |
| qa-smoke-tester | 2 |
| explorer | 2 |
| frontend-reviewer | 5 |
| code-reviewer | 3 |
| performance-reviewer | 4 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.
**Shared-file warning:** another session is concurrently working on 5.10 in this checkout — `apps/inventory/tests/conftest.py`
is dirty with THEIR changes: never revert, rewrite or commit it. Only additive surgical edits if ever needed.

### C1 — `templates/inventory/stocktake/physicalinventory/detail.html:88`

- **Found by:** frontend-reviewer
- **Lesson:** L33
- **Problem:** Line-item status badge uses semantic classes `badge-success` / `badge-danger`, which do not exist in static/css/theme.css, so counted/variance statuses render as unstyled plain text.
- **Fix:** Colour-named modifiers only — `badge-green` for counted/matched, `badge-red` for variance/out-of-tolerance, `badge-amber` for pending recount; verify each branch against `CycleCountTask.STATUS_CHOICES` exact values and keep a `{% else %}` fallback (`{{ sheet.get_status_display }}`). Grep theme.css before using any modifier class.
- **Status:** [ ] open

### I1 — `apps/inventory/models/StocktakingCycleCounting/CountPrograms.py:105`

- **Found by:** security-reviewer, qa-smoke-tester, explorer
- **Problem:** Same-day duplicate-run guard filters `notes=marker` (exact match) but `generate_tasks` persists sheets as `notes=f"{marker} · {self.name}"`, so the reuse lookup can never match its own prior sheet — every Run mints duplicate same-day blind count tasks (QA confirmed live: two consecutive POSTs produced CC-00035 + CC-00036 instead of reusing).
- **Fix:** Filter with `notes__startswith=marker` (mirroring the provenance query at views/StocktakingCycleCounting/CountPrograms.py:42), so the reuse branch is actually reachable again.
- **Status:** [ ] open

### I2 — `apps/inventory/views/StocktakingCycleCounting/CountPrograms.py:78`

- **Found by:** security-reviewer
- **Problem:** `countprogram_run` has no view-level or model-level `is_active` guard — a direct POST on a deactivated program mints count sheets for a program the tenant switched off (the hidden-button state is bypassable).
- **Fix:** Refuse in the view (flash message + redirect, or raise ValidationError surfaced like the PhysicalInventory verbs do) when `not obj.is_active`; also acceptable inside `generate_tasks()`.
- **Status:** [ ] open

### I3 — `templates/inventory/stocktake/physicalinventory/detail.html:12`

- **Found by:** security-reviewer
- **Lesson:** L42
- **Problem:** Start & Freeze button interpolates user-editable free text (`scm.Location.code`) into `onsubmit="return confirm('Freeze {{ obj.warehouse.code }} …')"` — HTML entities decode before the JS engine parses the attribute, so autoescaping cannot save it (`X');alert(document.cookie)//` executes; a benign `O'BRIEN` breaks the handler and freeze submits without confirmation).
- **Fix:** Remove Location-field interpolation from confirm() per L42 rule 1 — use a static message (optionally the system-assigned `{{ obj.number }}` in button label text), never a mutable field inside `confirm('…')`.
- **Status:** [ ] open

### I4 — `templates/inventory/stocktake/countprogram/form.html:61`

- **Found by:** frontend-reviewer
- **Problem:** `<label for="id_frequency">` has no matching control id — the rendered select/input lacks an explicit id, so screen readers don't associate label with control.
- **Fix:** Verify what Django actually renders for that field first; if the widget is hand-written, add `id="id_frequency"` to the control so it pairs with the existing `for=`. If the label/control already pair correctly (reviewer's own note was uncertain), mark skipped as not-a-defect with evidence.
- **Status:** [ ] open

### I5 — `templates/inventory/stocktake/variance.html:34`

- **Found by:** frontend-reviewer
- **Lesson:** L33
- **Problem:** Variance direction badge branches test only `> 0` / `< 0`; a perfectly matched zero-variance line falls into `{% else %}` rendering a red "Variance" badge — false status shown to users.
- **Fix:** Branch positive → red "Over", negative → amber "Under", and make `{% else %}` render green "Matched" (exact-zero case).
- **Status:** [ ] open

### I6 — `apps/inventory/models/StocktakingCycleCounting/PhysicalInventories.py:127`

- **Found by:** code-reviewer
- **Problem:** `start()`'s already-covered skip keys on notes prefix `"Physical inventory {number}"`, but `next_number()` restarts at PHY-00001 after a `--flush` re-seed while old spawned `scm.CycleCountTask`s survive — the re-seeded event adopts the previous generation's sheets (possibly all reconciled/cancelled), mints zero sheets and reports their statuses as its own coverage.
- **Fix:** Make the provenance marker unique to the row (e.g. include the event pk alongside the number) so a re-issued number can't collide across generations.
- **Status:** [ ] open

### I7 — `apps/inventory/models/StocktakingCycleCounting/CountPrograms.py:111`

- **Found by:** code-reviewer
- **Problem:** `generate_tasks()` performs three writes (mint CycleCountTask(s), stamp `last_run_date`, audit log) with no `transaction.atomic()` and no `select_for_update` — unlike every verb in sibling PhysicalInventories.py; two near-simultaneous Run POSTs both see no existing sheet and mint duplicates, defeating the reuse guarantee.
- **Fix:** Wrap the body in `with transaction.atomic():` and re-read the program row via `select_for_update()` (mirror `_locked()` in PhysicalInventories.py:100) before the existence probe.
- **Status:** [ ] open

### I8 — `apps/inventory/models/StocktakingCycleCounting/PhysicalInventories.py:133`

- **Found by:** performance-reviewer
- **Problem:** `start()` mints one `CycleCountTask.objects.create()` per bin/zone, each save running next_number's max+1 SELECT + INSERT while the event sits under `select_for_update` — a wall-to-wall count (hundreds–thousands of bins) serializes thousands of round trips inside one lock-holding transaction.
- **Fix:** Read the tenant's current max `CC-#####` number once, pre-assign numbers to local instances, insert all sheets with one `CycleCountTask.objects.bulk_create(...)`; keep the provenance marker identical so I6/I1 lookups still match bulk-created rows.
- **Status:** [ ] open

### M1 — `templates/inventory/stocktake/countprogram/list.html:56`

- **Found by:** security-reviewer
- **Lesson:** L42
- **Problem:** Static apostrophe written as `today&apos;s` inside the Run-now `onsubmit` — HTML-decodes back to a bare `'` terminating the JS string literal, throwing on every click so the form submits with NO confirmation dialog.
- **Fix:** Escape for JS, not HTML: `today\'s`.
- **Status:** [ ] open

### M2 — `apps/inventory/management/commands/seed_inventory.py:1257`

- **Found by:** qa-smoke-tester, explorer
- **Problem:** Seeder success message hardcodes "{done.number} reconciled." though the seeded demo walk ends `cancelled` (start→cancel), and prints "counting" for `live` even if its `start()` raised ValidationError.
- **Fix:** Print real statuses derived from the objects, e.g. `f"{done.number} {done.get_status_display().lower()}"`.
- **Status:** [ ] open

### M3 — `apps/inventory/models/StocktakingCycleCounting/CountPrograms.py:40`

- **Found by:** code-reviewer
- **Problem:** Dead code: `STATUS_CSS` dict on both models (also PhysicalInventories.py:43) has no `status_css` property consuming it; templates hard-code the Active/Inactive badges instead.
- **Fix:** Delete both unused dicts, or add the conventional `status_css` property and use it in list/detail templates like crossdockorder/reservation do (pick one style, don't do both).
- **Status:** [ ] open

### M4 — `templates/inventory/stocktake/countprogram/list.html:12`

- **Found by:** frontend-reviewer
- **Lesson:** L2
- **Problem:** Claimed multi-line `{# #}` comment block leaking raw `{#` text into rendered HTML above the table header (Django single-line comments don't span newlines). NOTE: qa-smoke-tester's rendered-HTML sweep found ZERO `{#` leaks on this page — verify against actual rendered output before changing anything; if the sweep is right, mark skipped as not-a-defect with that evidence.
- **Fix:** If confirmed: convert to per-line single-line comments or `{% comment %}…{% endcomment %}`.
- **Status:** [ ] open

### M5 — `templates/inventory/stocktake/physicalinventory/list.html:29`

- **Found by:** frontend-reviewer
- **Problem:** Empty-state block shows only "No physical inventories found." with no call-to-action link to the create form, unlike the countprogram list.
- **Fix:** Append an anchor to `inventory:physicalinventory_create` inside the empty-state div, matching the countprogram pattern.
- **Status:** [ ] open

### M6 — `apps/inventory/views/StocktakingCycleCounting/PhysicalInventories.py:39`

- **Found by:** performance-reviewer
- **Problem:** Detail view issues two separate COUNT queries over the same spawned-sheets queryset (`sheets.count()` then filtered count).
- **Fix:** Collapse to one query: `sheets.aggregate(total=Count("id"), reconciled=Count("id", filter=Q(status="reconciled")))`.
- **Status:** [ ] open

### M7 — `apps/inventory/models/StocktakingCycleCounting/PhysicalInventories.py:67`

- **Found by:** performance-reviewer
- **Problem:** Default ordering `["-scheduled_date", "-id"]` but migration 0015 ships only `(tenant, status)` index — every paginated list render filesorts the tenant's rows.
- **Fix:** Add `models.Index(fields=["tenant", "-scheduled_date"], name="inv_phy_tnt_sched_idx")` to Meta.indexes + matching incremental migration (agree the number with any concurrent session before generating — check `ls apps/inventory/migrations/` first).
- **Status:** [ ] open

### M8 — `apps/inventory/models/StocktakingCycleCounting/PhysicalInventories.py:81`

- **Found by:** performance-reviewer
- **Problem:** Provenance lookups (`spawned_tasks()`, the generate_tasks duplicate check, countprogram_detail recent-tasks filter) do left-anchored `notes__startswith` against `scm.CycleCountTask.notes`, an unindexed TextField — full-scans on every detail render / program run.
- **Fix:** Prefer bounding the scan with a date/window condition inside inventory's own query over touching the spine's schema; if schema change chosen instead, `db_index=True` on `scm.CycleCountTask.notes` needs an scm migration (coordinate with concurrent sessions).
- **Status:** [ ] open

## Notes — app-wide / pre-existing (NOT in the fix queue)

- **security-reviewer:** lifecycle verbs correctly wrap select_for_update in atomic with model-level guards surfaced as flash messages; `next_number()` non-atomic max+1 numbering is pre-existing (documented in apps/core/utils.py); seeder `--flush` deletes across tenants, consistent with every sibling seeder's flush contract.
- **explorer:** marker prefix-collision (PHY-0001 matches PHY-00010) only past 99,999 documents given fixed-width numbering — KNOWN LIMIT family of `next_number`; unused `today` key in countprogram_list extra_context; detail template dereferences `sheet.adjustment.number` without select_related on spawned_tasks (folded into M-lane perf findings context); `manage.py check` clean.
- **code-reviewer:** choice-value alignment verified end-to-end (frequency/status/method vs CycleCountTask choices, boolean filters vs crud_list mapping); context contracts satisfied (obj/recent_tasks/is_due; obj/sheets/sheet_total/sheet_reconciled; rows/page_obj/q/status); `coverage` property exercised only by tests while the detail view recomputes inline; migration 0015 matches models field-for-field (`makemigrations --check` clean); all 15 routes reverse.
- **performance-reviewer:** `due_today = [p for p in qs if p.is_due(...)]` eagerly evaluates ALL programs before crud_list applies search/filters/pagination — pure Python so no N+1, harmless at program scale, worth knowing it bypasses pagination; variance_report selects location+adjustment up front (zero extra queries rendering row.task.adjustment.number).

## Done well

- **security-reviewer:** Cross-tenant defense thorough and consistent — every pk lookup via get_object_or_404 scoped by request.tenant; forms pair narrowed tenant-scoped FK querysets with `_reject_foreign()` clean() re-checks; system fields (status, is_frozen, requested_by, number) excluded from Meta.fields — no mass assignment anywhere.
- **qa-smoke-tester:** Freeze lifecycle genuinely safe end-to-end — reconcile refuses while any spawned sheet is open and NAMES the blocking sheet numbers; verified live through SCM's own counted→reconcile path posting ADJ-00003 (reason=cycle_count) and correctly lifting the freeze.
- **explorer:** All four re-export layers complete and consistent (models/forms/views packages + parent inits + urls aggregation) — no ImportError/reverse failure anywhere in the chain.
- **frontend-reviewer:** countprogram status filter reflects request.GET persistence with |stringformat:"d" pk comparison; every Actions column carries working view/edit/delete; detail pages include complete Actions sidebars mirroring sibling modules.
- **code-reviewer:** Migration 0015 matches models exactly; tenant scoping universal; verbs use FOR UPDATE + atomic with a reconcile guard naming blocking sheets.
- **performance-reviewer:** variance_report pre-selects both FKs up front avoiding exactly the N+1 trap its sibling fell into; delete guard uses spawned_tasks().exists() instead of materializing rows.
