# Review findings — inventory 5.10 Returns Management (RMA)

Range: `094635e2...HEAD` (scoped to ReturnsManagement paths + templates/inventory/returns + test_returns_* + conftest returns fixtures) · Generated: 2026-08-23
Wave (parallel): code-reviewer · explorer(contract) · frontend-reviewer · performance-reviewer · qa-smoke-tester · security-reviewer
Runtime at wave time: smoke_returns.py ALL PASS · run_returns_tests.py 16/16 · extended junk-param/pagination/member/no-rule sweeps ALL PASS.

## Summary

| Severity | Count |
|---|---|
| Critical | 1 |
| Important | 6 |
| Minor | 13 |
| **Total (deduped)** | **20** |

| Agent | Raw findings |
|---|---|
| code-reviewer | 6 |
| explorer | 2 |
| frontend-reviewer | 9 |
| performance-reviewer | 7 |
| qa-smoke-tester | 0 failures / 3 improvement notes |
| security-reviewer | 1 |

## How to work this file (code-fixer)

Fix in ID order: every `C`, then every `I`, then every `M`. One fix → one file → one `git add` + one
`git commit`. Update each **Status** line to `[x] fixed — <commit subject>` or `[~] skipped — <reason>`
as you go. Never delete a finding; a wrong one gets `[~] skipped — not a defect: <why>`. Never `git push`.

**Scope guard (concurrent session!):** a sibling session is building 5.11 Stocktaking & Cycle Counting in this
same checkout. Touch ONLY the files named in these findings (plus their package `__init__.py` if an export must
change). Never edit anything under `StocktakingCycleCounting/`, never rewrite shared files wholesale — surgical
edits only. Sandbox cannot run pytest/create_test_db ("ChildProcess.kill"): verify with
`venv\Scripts\python.exe manage.py check`, `temp\smoke_returns.py` and `temp\run_returns_tests.py` instead.

## Critical

### C1 — `templates/inventory/returns/dispositionrule/detail.html:67`

- **Found by:** explorer
- **Problem:** `{% url 'scm:category_detail' obj.category.pk %}` — that route does not exist anywhere in
  `apps/scm/urls` (only category_list/create/edit/delete); any category-pinned rule's detail page raises
  NoReverseMatch → 500.
- **Fix:** render the category as plain text (`{{ obj.category.name }}`) instead of a cross-app link — do not
  add routes to the SCM app from Module 5 (L36). Same for any other dead link on that page.
- **Status:** [x] fixed — fix(inventory): 5.10 C1 render pinned category as plain text - scm:category_detail route does not exist so any category-pinned rule detail raised NoReverseMatch/500; no SCM routes added from Module 5 (L36)

## Important

### I1 — `templates/inventory/returns/returninspection/form.html`

- **Found by:** explorer
- **Problem:** `return_disposition` is in `ReturnInspectionForm.Meta.fields` and prefilled from `?disp=` by
  the view, but never rendered — POST drops it, so inspections created from the workbench save with NULL
  disposition and the bench's `has_inspection` lookup (`return_disposition=disp`) can never match: "Pending QA"
  never flips to "Inspected".
- **Fix:** render the bound field hidden inside the form, e.g.
  `<input type="hidden" name="return_disposition" value="{{ form.return_disposition.value|default:'' }}">`
  (the visible picker stays out of the layout by design; the queryset scoping already guards tenancy).
- **Status:** [x] fixed — fix(inventory): 5.10 I1 carry prefilled return_disposition through the POST as a hidden input - the field lives in Meta.fields but has no visible picker, so bench-prefilled inspections saved with NULL disposition and the workbench has_inspection lookup could never match

### I2 — `apps/inventory/views/ReturnsManagement/ReturnInspections.py:101`

- **Found by:** code-reviewer
- **Problem:** on CREATE only `form.is_valid()` gates the atomic block; an invalid checklist formset is
  silently skipped while the inspection saves and a success flash fires — typed checkpoints are silently
  discarded (EDIT path correctly requires both).
- **Fix:** gate on `if form.is_valid() and formset.is_valid():`.
- **Status:** [x] fixed — fix(inventory): 5.10 I2 gate inspection CREATE on formset.is_valid() too - an invalid checklist formset was silently skipped while the inspection saved and a success flash fired, discarding typed checkpoints (edit path already required both)

### I3 — `apps/inventory/views/ReturnsManagement/ReturnInspections.py:71-86`

- **Found by:** code-reviewer
- **Lesson:** L11
- **Problem:** `?rma=`, `?line=`, `?disp=` go into `.filter(pk=…)` after only `.strip()` — `?rma=abc` or an
  over-range integer raises ValueError/driver error → 500 from the address bar.
- **Fix:** parse each with `as_db_int(...)` from `apps.core.crud` and skip the lookup when None.
- **Status:** [x] fixed — fix(inventory): 5.10 I3 parse ?rma= ?line= ?disp= with as_db_int - non-numeric or over-range pk params from the address bar raised ValueError/driver 500s instead of skipping the prefill lookup (L11)

### I4 — `templates/inventory/returns/*.html` (12 sites)

- **Found by:** frontend-reviewer
- **Lesson:** L33
- **Problem:** `text-primary` exists nowhere (theme.css defines `.text-brand`; Tailwind config adds no
  `primary` color) — all document-number/SKU/location links render unstyled.
- **Fix:** replace all 12 occurrences with the existing `.text-brand`.
- **Status:** [x] fixed — fix(inventory): 5.10 I4 text-primary to text-brand across returns templates (5 file commits b766be13/05defd6d/df10333f/4c352555/3f47d6b3) — 11 sites swapped (the 12th died with C1's dead link); `rg text-primary templates/inventory/returns` now matches nothing

### I5 — `templates/inventory/returns/returninspection/form.html:155,160,165`

- **Found by:** frontend-reviewer
- **Problem:** formset row labels ("Checkpoint"/"Result"/"Notes") have no `for=` attribute — label→input
  association broken across repeated rows.
- **Fix:** `for="{{ ck_form.checkpoint.id_for_label }}"` etc. on the three labels.
- **Status:** [x] fixed — fix(inventory): 5.10 I5 add for= to checkpoint/result/notes formset row labels - label-input association was broken across every repeated inline row

### I6 — `apps/inventory/views/ReturnsManagement/ReturnInspections.py:23`

- **Found by:** performance-reviewer
- **Problem:** list `select_related` omits `return_authorization__customer` while every row renders
  `obj.return_authorization.customer.name` → N+1 per page (detail view already does this).
- **Fix:** extend select_related to `"return_authorization__customer"`.
- **Status:** [x] fixed — fix(inventory): 5.10 I6 extend inspection list select_related with return_authorization__customer - every register row prints the customer name, so the omission cost an N+1 per page (detail view already fetched it)

## Minor

### M1 — `apps/inventory/models/ReturnsManagement/DispositionRoutingRules.py:138`

- **Found by:** security-reviewer
- **Problem:** `resolve_disposition_routing(rules=<explicit>)` trusts the caller's list without asserting
  tenancy — latent leak if a future caller passes unfiltered rules.
- **Fix:** when `rules` is provided, filter `[r for r in rules if r.tenant_id == effective_tenant.pk]`
  (cheap, keeps both call sites working).
- **Status:** [x] fixed — fix(inventory): 5.10 M1 tenancy-filter caller-supplied rules in resolve_disposition_routing - an explicit rules list was trusted wholesale, a latent cross-workspace leak if a future caller passed unfiltered rows

### M2 — `templates/inventory/returns/workbench.html:77`

- **Found by:** code-reviewer
- **Problem:** bench header badge shows `{{ bench_items|length }}` (capped at 20) next to a KPI card showing
  the true `stats.awaiting_bench` — contradictory numbers once >20 rows sit on the bench.
- **Fix:** print `{{ stats.awaiting_bench }}` in the header badge.
- **Status:** [x] fixed — fix(inventory): 5.10 M2 bench header badge prints stats.awaiting_bench - it showed the capped 20-row slice length beside a KPI card with the true total, contradicting it once more than 20 rows sat on the bench

### M3 — `apps/inventory/views/ReturnsManagement/ReturnsWorkbench.py:69-78,37`

- **Found by:** code-reviewer + performance-reviewer
- **Problem:** one `.exists()` per pending disposition (unbounded bench set) and the RMA prefetch carries two
  dead legs (`lines__item__category`, `lines__dispositions`) while missing the reverse relation the template
  loops over (`inventory_inspections`, workbench.html:254).
- **Fix:** batch the inspection check into one `values_list("return_disposition_id", flat=True)` query for
  the fetched dispositions; prefetch exactly `"lines__item"` and `"inventory_inspections"`.
- **Status:** [x] fixed — fix(inventory): 5.10 M3 batch bench has_inspection into one values_list query and fix RMA prefetch - the per-disposition .exists() scaled with the unbounded bench set, and the prefetch carried two dead legs while missing the inventory_inspections relation the template loops over

### M4 — `apps/inventory/management/commands/seed_inventory.py:1073`

- **Found by:** code-reviewer
- **Problem:** seeded `quantity` falls back to `Decimal("1.0000")` only when there is no line; a line with a
  falsy `quantity_approved` seeds 0, violating the model's MinValueValidator on any later edit-form save.
- **Fix:** `qty = getattr(line, "quantity_approved", None) or Decimal("1.0000")` style guard (never 0).
- **Status:** [x] fixed — fix(inventory): 5.10 M4 guard seeded inspection quantity against falsy quantity_approved - a 0-approval line seeded quantity=0, violating the model MinValueValidator on any later edit-form save; falls back to one unit

### M5 — `apps/inventory/forms/ReturnsManagement/ReturnInspections.py` clean()

- **Found by:** code-reviewer
- **Problem:** when both `return_disposition` and `return_line` are set they are never cross-checked — a
  same-tenant disposition from a different RMA can be attached.
- **Fix:** in `clean()`, when both are present verify
  `cleaned["return_disposition"].return_line_id in (None, cleaned["return_line"].id)` and add a
  `return_disposition` field error otherwise.
- **Status:** [x] fixed — fix(inventory): 5.10 M5 cross-check return_disposition against return_line in clean() - a same-tenant disposition from a different RMA could be attached to an inspection; now a field error (line-less dispositions still allowed)

### M6 — `apps/inventory/views/ReturnsManagement/ReturnInspections.py:27-37` (+ DispositionRoutingRules.py)

- **Found by:** qa-smoke-tester
- **Problem:** junk filter values (`status=zzz`, emoji grades) pass through exact-match filters safely but
  are echoed back into context, rendering a silently empty register instead of being rejected.
- **Fix:** validate each GET filter against its CHOICES list and fall back to "" when unmatched.
- **Status:** [x] fixed — fix(inventory): 5.10 M6 validate inspection list GET filters against their CHOICES - junk values like status=zzz or emoji grades passed the exact-match filter but echoed back into context, rendering a silently empty register

### M7 — display-label fallbacks in templates

- **Found by:** frontend-reviewer
- **Problem:** several `{% else %}` branches hardcode labels instead of `get_*_display`: list.html:161
  "Pending"; list.html:141/detail.html:108 "Untested"; detail.html:182 checklist "N/A";
  workbench.html:147 `{{ item.suggested_disposition|title }}` can print raw codes (`received_pending`);
  workbench.html:125 `{{ item.condition_grade|upper }}` prints "A".
- **Fix:** use `{{ obj.get_status_display }}` / `{{ obj.get_functional_status_display }}` /
  `{{ ck.get_result_display }}`; for the workbench dict-row values compute display strings in the view
  (`dict(ReturnDisposition.DISPOSITION_CHOICES).get(value, value)` etc.) and print those.
- **Status:** [x] fixed — 4 commits: fix(inventory): 5.10 M7 compute bench display strings in the view (81301536) / workbench else badges print view-computed display labels (119dad11) / inspection register else badges use get_*_display (7938d703) / inspection detail else badges use get_*_display (ba1c90ac)

### M8 — `templates/inventory/returns/dispositionrule/detail.html:104`

- **Found by:** frontend-reviewer
- **Problem:** suggested_disposition rendered as a fixed `badge-info` regardless of value — Scrap/Quarantine
  appear calm-blue here but red/slate on the module's own list page.
- **Fix:** reuse the list page's colour branch.
- **Status:** [x] fixed — fix(inventory): 5.10 M8 rule detail reuses the list page suggested-disposition colour branch - Scrap/Quarantine showed calm badge-info on the detail while the module list renders them red/slate

### M9 — KPI strips use `grid grid-cols-4 gap-4`

- **Found by:** frontend-reviewer
- **Problem:** workbench.html:25 and returninspection/list.html:22 use a fixed 4-col grid where sibling
  inventory stat pages use the responsive `.stat-grid` wrapper.
- **Fix:** switch both wrappers to `class="stat-grid"`.
- **Status:** [x] fixed — fix(inventory): 5.10 M9 workbench KPI strip switches to the responsive stat-grid wrapper (908e1bd7) + inspection register KPI strip switches to the responsive stat-grid wrapper (05870597)

### M10 — dark-mode tint leaks

- **Found by:** frontend-reviewer
- **Problem:** detail.html:248 (`bg-slate-50 … border-slate-200` routing panel) and form.html:152
  (`border-slate-100`) stay light under `html.dark`.
- **Fix:** replace with theme-var-styled containers (`.card`-style border/background classes that exist in
  theme.css) or drop the tint.
- **Status:** [x] fixed — fix(inventory): 5.10 M10 route-reason panel drops light-only slate tint for theme-var background/border (2eb68ff4) + checklist row separators use var(--border) (570a30a6)

### M11 — grouped KPI COUNTs

- **Found by:** performance-reviewer
- **Problem:** ReturnInspections list runs 4 separate COUNTs + paginator count; workbench repeats the RMA
  count and splits passed/quarantined into two COUNTs.
- **Fix:** one `values("status").annotate(n=Count("id"))` per source mapped into the stats dicts (house
  pattern, cf. PhysicalInventories.py:41).
- **Status:** [x] fixed — fix(inventory): 5.10 M11 inspection register KPIs from one values(status) grouped COUNT (b8259f04) + workbench stats from grouped values(status) counts (8a470e27)

### M12 — workbench search fan-out

- **Found by:** performance-reviewer
- **Problem:** search OR across `lines__item__*` fans out rows and needs `.distinct()` whose cost lands on
  Paginator.count for every searched page.
- **Fix:** replace the two line-item clauses with `Exists()` subqueries and drop `.distinct()` (keep
  number/customer inline).
- **Status:** [x] fixed — fix(inventory): 5.10 M12 workbench item search runs as a correlated EXISTS - the lines__item OR clauses fanned out rows and needed .distinct() whose cost landed on Paginator.count for every searched page

### M13 — no member user per tenant in dev seed

- **Found by:** qa-smoke-tester
- **Problem:** no non-admin Acme/Globex user exists out of the box, so member-gating 403 paths are only ever
  exercised by ad-hoc scripts.
- **Fix:** have `seed_inventory` ensure one plain staff-free member user per demo tenant
  (e.g. `member_acme`/`member_globex`, password `password`). Surgical addition to the existing per-tenant
  loop; coordinate with any sibling-session seeder edits (touch only your own block).
- **Status:** [~] skipped — not a defect: `seed_accounts` already ensures two staff-free Member-role users per tenant (`sales_<slug>`, `ops_<slug>`, password "password" — apps/accounts/management/commands/seed_accounts.py:78-84), and the login view accepts username-or-email identifiers, so member-gated 403 paths ARE exercisable out of the box. The observed gap is stale dev data (acme tenant postdates the last seed_accounts run: sales_globex/ops_globex exist, sales_acme/ops_acme do not), repaired by re-running `seed_accounts` — minting identity rows in a module seeder would duplicate seed_accounts' job under a third naming convention

## Notes — app-wide / pre-existing (NOT in the fix queue)

- **qa-smoke-tester:** `apps/core/crud.py` paginate clamps out-of-range pages to the last page (200 with
  duplicated content) instead of Http404 — pre-existing house behaviour across every module, SEO nit only.
- **performance-reviewer:** workbench materializes the whole `received_pending` set before `[:20]`;
  acceptable while the bench is a working queue — revisit if undecided dispositions accumulate.
- **performance-reviewer:** `functional_status` list-filter column lacks a `(tenant, functional_status)`
  index — only worth a migration past ~100k rows; needs migration-number coordination anyway.
- **security-reviewer:** inspection edit exposes status transitions to any staff member — consistent with
  module convention, authorization-design observation only.
- **code-reviewer:** Django-admin TabularInline over TenantOwned children renders a raw tenant select —
  admin-only cosmetic, app-wide pattern.
- **frontend-reviewer:** pervasive inline `style="font-size:…px"` sizing (~15 sites) where siblings use
  text-xs/text-sm — cosmetic inconsistency.

## Done well

- **code-reviewer:** `resolve_disposition_routing()` is a genuinely correct specificity resolver (tier →
  grade specificity → priority/id), honest None-tuple refusals, suggestion vocabulary a strict subset of
  SCM 4.10's DISPOSITION_CHOICES — zero choice-value drift anywhere in the sub-module.
- **security-reviewer:** the tenant-less `scm.ReturnLine` spine is handled redundantly and consistently
  (queryset scoped via `return_authorization__tenant`, parent-RMA guards at BOTH form and model boundary),
  documented so nobody "fixes" it wrong later; deletes are decorator-gated AND method-gated.
- **explorer:** zero re-declaration of the SCM spine — the module reads/writes scm documents directly and
  LIVE_LINKS["5.10"] maps every bullet onto live routes.
- **qa-smoke-tester:** junk params, emoji grades, page=99, SQL-ish q strings — all 200 with autoescape
  holding; SMOKETEST rows fully cleaned up after the sweep.
