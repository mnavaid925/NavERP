# Review — Projects 7.19 Master Data & Configuration

- **Scope:** `3e10760acea9757261c6e5f45ec85e119fda5d09` through the 7.19 changes present at fixer start, including current uncommitted 7.19 corrections
- **Reviewers:** code reviewer → explorer → frontend reviewer → performance reviewer → QA smoke reviewer → security reviewer
- **Smoke baseline:** initial gate 182/182 passed; independent QA probe 242/267 passed with six reproducible defects
- **Excluded:** concurrent 7.18 IntegrationApiHub, 7.16 reporting, Module 0/core, Sales, documentation, and unrelated untracked test changes
- **Status:** open findings below; the fixer must mark every item fixed or explicitly skipped with a reason

## Critical

- [x] **C1 — Tenant configuration mutation authorization bypass** fixed — every configuration mutation is tenant-admin gated server-side, POST-only method ordering is preserved, and member UI controls are hidden; 15/15 authorization assertions passed.
  - Sources: code C1, frontend F-C1, QA Q-C1, security S-C1
  - All create/edit/toggle/member/default routes in the four 7.19 entity view modules.
  - Ordinary members can mutate tenant-wide templates, custom fields, teams, memberships, and locale defaults. Gate every configuration write with `tenant_admin_required`; keep POST decorator order `@login_required` → `@require_POST` → `@tenant_admin_required`; retain member reads and intended member-level template instantiation; hide unauthorized controls.

- [x] **C2 — Every new locale-profile POST raises `ValueError`** fixed — the bounded field is now named `working_days_pattern`, values are coerced before model validation, and the real field renders errors; valid/invalid form and rendered-error probes passed.
  - Sources: QA Q-C2, security S-I3
  - `apps/projects/forms/MasterDataConfiguration/ProjectLocaleSettings.py:17`
  - `apps/projects/models/MasterDataConfiguration/ProjectLocaleSettings.py:131`
  - The form field is named `working_days_choices` while model validation errors target omitted `working_days_pattern`. Use one correctly named bounded MultipleChoice field, coerce values for persistence, and render field errors.

- [x] **C3 — Custom Fields & Forms is metadata-only and duplicates the core custom-field spine** fixed — `ProjectCustomField` now synchronizes idempotently to `core.CustomFieldDefinition`, persists values only in `core.CustomFieldValue`, and the reusable mixin is integrated into the real Project, Task, Milestone, Risk, and Team forms plus their form/detail templates. Visibility, required/type/regex/range/choice/URL/user-reference rules, edit loading, blank clearing, tenant isolation, and definition deactivation are enforced. The duplicate `task.story_points` seed was removed. Rollback-only probe: 27/27 assertions passed with no debris.
  - Sources: explorer C1, frontend F-I1
  - `apps/projects/models/MasterDataConfiguration/ProjectCustomFields.py:12`
  - `apps/core/models/CustomField.py:18`
  - `apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py:134`
  - Definitions are not rendered, persisted, or validated on target entities, while core already owns definition/value storage. The seeder also defines `task.story_points` although the real task column exists. Reuse/extend the core spine (or a typed project extension), wire project/task/milestone/risk/team forms and values, validate/apply visibility rules, and remove the duplicate story-point definition.

## Important

- [x] **I1 — Reject tenant-less create requests before form construction** fixed — all four create routes guard before any form work, and tenant-owned selector querysets default to `.none()`; 8/8 guard assertions passed.
  - Sources: explorer I7, QA Q-I3, security S-I1
  - All four 7.19 create views/forms.
  - A tenant-less account can see unscoped tenant-owned choices and submit a null-tenant row, causing disclosure or 500. Add a tenant guard before GET/POST handling; initialize tenant-owned querysets to `.none()` defensively.

- [x] **I2 — Make `pls_set_default` the sole, serialized, lifecycle-safe default writer** fixed — the form/admin no longer write `is_default`; the admin-only POST promotes into core `LocaleProfile`/`BusinessCalendar` under a tenant lock with post-lock lifecycle rechecks and a deterministic clear-and-set; valid, project-scoped, inactive, and single-default probes passed.
  - Sources: code I1/I3, frontend F-I8, QA Q-I2, security S-I2
  - `ProjectLocaleSettingForm` and `pls_set_default`.
  - Remove `is_default` from the ModelForm; refuse project-scoped and inactive targets; serialize on one common lock, reload/recheck after locking, and update all candidates deterministically. Hide invalid controls and show bound form errors.

- [x] **I3 — Enforce a complete bounded WBS schema before persistence and child creation** fixed — one exact-key/type/choice/length validator now guards forms and every model save, raw size/depth are bounded, JSON recursion becomes a field error, and instantiation revalidates after locking; 7 attack cases, valid normalization, and zero-row replay refusal passed.
  - Sources: code I4, explorer I5, QA Q-I1, security S-I4
  - ProjectTemplate form/model and `ptm_instantiate`.
  - Whitelist supported keys; require real booleans; validate exact 7.2 estimation/confidence choices and field lengths; reject malformed legacy/admin rows defensively; cap JSON size/depth and schedule span; catch parser recursion as field errors.

- [x] **I4 — Generate WBS dates from the effective business calendar and configured hours** fixed — WBS scheduling now resolves project override → core calendar, skips tenant holidays, advances configured workdays, derives effort from configured hours, and falls back honestly to calendar days/no effort; Friday→Monday, early-target rollback, fallback, and 7.50-hour effort probes passed.
  - Sources: code I5, explorer I5, frontend F-I2
  - `ProjectTemplate.estimated_duration_days` help text and WBS instantiation.
  - Resolve project override → core tenant locale/business calendar, advance only configured working days, derive effort from configured daily hours, and reject/align an explicit end date that predates the generated WBS. If no operational calendar can be resolved, make the contract and UI honestly calendar-day based instead of claiming business-day enforcement.

- [x] **I5 — Stop calling a draft instantiated Project “chartered”** fixed — the instantiate page, button, form help, success message, and audit path now say draft creation and explicitly require 7.1 charter submission/approval.
  - Sources: explorer I4, frontend F-I3
  - `template/instantiate.html`, instantiate success message, and related copy.
  - Describe the action as creating a draft that still requires 7.1 charter submission/approval, unless the action deliberately routes through those verbs.

- [x] **I6 — Make template default selection concurrency-safe** fixed — model save now serializes default changes on the tenant row, rechecks uniqueness after locking, and create/edit surface late conflicts as `is_default` form errors; the bound conflict probe passed.
  - Sources: code I2
  - `ProjectTemplateForm` create/edit and model default validation.
  - Serialize default changes on a common lock, recheck uniqueness inside the transaction, and surface bound field errors. Do not edit migration history to fake a conditional unique constraint unsupported by MariaDB.

- [x] **I7 — Make team-member writes valid, bound, and race-safe** fixed — membership forms stamp tenant before model validation, the inline form does the same, duplicate validation renders in place, and the save path catches the unique-race `IntegrityError` without redirecting; stamping, duplicate, and mocked-race probes passed.
  - Sources: code I7/I9, explorer I8, frontend F-I7
  - `ProjectTeamMemberForm`, `pte_add_member`, and the team admin inline.
  - Stamp/scope tenant before validation in both UI and admin; catch the DB uniqueness race in a nested atomic block; re-render bound member values/errors rather than redirecting to a blank form.

- [x] **I8 — Make departed membership historical rather than active staffing** fixed — current staffing/allocation/list counts use `left_date__isnull=True`, departure is a locked historical stamp rather than delete, current and historical registers are separately paginated, and the departure probe preserved the row and rendered history.
  - Sources: code I8, frontend F-I9
  - Team list/detail/hub counts, total allocation, and `ProjectTeamMember.left_date`.
  - Use `left_date__isnull=True` for current staffing/allocation, expose historical membership separately or add a controlled departure action, and stop hard-deleting the only history trail.

- [x] **I9 — Hand team staffing to the 7.3 resource spine** fixed — team membership is explicitly a roster view; project members and template roles hand off to 7.3 `ResourceAllocation` placeholders, with `User.party` matched to `ResourceProfile.employee__party`/`party` when a real bookable identity exists, and shared teams remain roster-only.
  - Sources: explorer I2
  - `ProjectTeamMember`, `ResourceProfile`, `ResourceAllocation`, and template default roles.
  - Link membership to bookable resource identities where applicable; keep date-window/magnitude demand in 7.3; materialize template roles as 7.3 placeholders/demand or provide a clear handoff so capacity boards see template staffing. Preserve external `core.Party` support for vendor teams if the product scope retains them.

- [x] **I10 — Make locale settings project overrides over core 0.15, not a competing default source** fixed — project settings are now override-only operational rows, one active override is enforced, `pls_set_default` promotes into core `LocaleProfile`/`BusinessCalendar`, and the exported `resolve_project_locale` is consumed by 7.19 WBS scheduling rather than creating a second default source. Sibling 7.2/7.4/7.15 consumers remain their owners and were not duplicated.
  - Sources: explorer I1
  - `ProjectLocaleSetting`, `core.LocaleProfile`, `core.BusinessCalendar`, and project scheduling/financial consumers.
  - Restrict workspace defaults to core, enforce one unambiguous active override per project, inherit missing values from core locale/calendar, and expose/use a resolver in the relevant 7.2/7.4/7.15 consumers.

- [x] **I11 — Materialize or consume template workflow configuration through 7.17** fixed — workflow JSON now has a bounded exact schema, and instantiation creates real 7.17 `ProjectWorkflowRule` and `ProjectApprovalGate` rows (with missing milestone targets rolling back); 2/2 materialization and rejection probes passed.
  - Sources: explorer I3
  - `ProjectTemplate.workflow_config` and `ptm_instantiate`.
  - Define a validated schema and materialize `ProjectWorkflowRule`/approval gates, or add a durable template reference consumed by 7.17; do not leave stage-gate JSON display-only.

- [~] **I12 — Reconcile sibling contracts that parked reusable policy to 7.19** skipped — code inspection shows WIP limits remain 7.8 task-board policy, risk appetite remains 7.5 `TOLERANCE_BANDS`, quality standards/checklists remain 7.6 fields/library, and scope-change thresholds remain 7.7 constants. The 7.19 frozen model/contract owns none of those ledgers; adding them here would duplicate sibling owners, and this fixer is explicitly forbidden to edit the sibling contracts/forms. No 7.19 template claims those policies operationally, so the misleading-copy concern is not present.
  - Sources: explorer I6
  - Kickoff agendas, task-board WIP limits, risk appetite, quality standards/checklists, and scope-change thresholds.
  - Wire typed configuration where required by current NavERP bullets, or explicitly reassign/defer each concern and update the sibling contracts. Do not mark 7.19 live while a claimed 7.19 consumer remains permanently empty/contradictory.

- [x] **I13 — Restore the frozen seeder guard without duplicating canonical rows** fixed — any existing 7.19 row returns immediately with the standard warning, new data uses bounded selections/lookups and the non-native task field, and two no-flush seed runs produced identical counts for all five 7.19 tables across all tenants.
  - Sources: code I6, explorer M1, frontend/perf seeder notes
  - `seed_projects._master_data_configuration`.
  - Existing 7.19 data must produce a no-op with the standard “Data already exists. Use --flush to re-seed.” warning. New tenant data must use the consumable nested WBS schema and stable lookups. Bound user/project selection instead of materializing whole tables.

- [x] **I14 — Bound WBS instantiation database work** fixed — numbered phase/child rows are allocated once and written with 500-row `bulk_create`/`bulk_update` while preserving parent links, milestones, tenant scope, and atomicity; a 2,100-task maximum probe used 11 SQL statements.
  - Sources: performance P1
  - `_instantiate_wbs`.
  - A maximum accepted template currently generates roughly 4,303–4,305 statements. Allocate numbered rows in bounded batches and use `bulk_create`/`bulk_update` while preserving parent links, milestones, atomicity, and tenant scoping.

- [x] **I15 — Reduce hub/list query and hydration overhead** fixed — hub counts are consolidated into one aggregate per owned model, team member counts use correlated subqueries, current-only staffing is indexed by predicate, list/admin querysets defer heavyweight JSON/Text, and bounded selector rows are used; hub rendered in 10 domain queries and team list in 11 total client queries.
  - Sources: performance P2/P3/P4
  - Configuration hub, template/custom-field lists, team list, and admin changelists.
  - Consolidate hub counts, replace grouped member counts with bounded correlated subqueries, and defer heavyweight JSON/Text and unused joins on list/hub/admin querysets without breaking rendered fields.

- [x] **I16 — Restore theme-safe and responsive 7.19 presentation** fixed — all 14 owned templates use verified theme/CDN classes, logical direction utilities, dark-safe text/surface/border utilities, wrapped action headers, and the invalid `primary`/`form-checkbox` families are gone; source scan is clean.
  - Sources: frontend F-I4/F-I5
  - All 14 templates and actual Tailwind/theme configuration.
  - Verify the reported missing `primary` utilities against the live CDN configuration; replace/define them once. Add dark-mode-safe text/surfaces and narrow-screen action/grid behavior without inventing CSS classes.

## Minor

- [x] **M1 — Use the frozen audit verbs** fixed — instantiation audits `instantiate` and default promotion audits `set_default`; both are within the 10-character contract.
  - Source: code M1
  - Instantiate must audit `instantiate`; set-default must audit `set_default`; both fit the 10-character limit.

- [x] **M2 — Make recent/paginated ordering deterministic** fixed — hub recent rows and team lists use `-id` tie-breakers, and locale lists explicitly order by default/name/id.
  - Source: code M2
  - Hub recent rows and locale ordering need final `-id` tie-breakers.

- [x] **M3 — Render zero-valued custom-field bounds correctly** fixed — the detail view uses an explicit `has_numeric_bounds` property, so `Decimal("0.00")` renders as a real bound.
  - Sources: explorer M3, frontend F-M3, QA Q-M1
  - Pass explicit nullness flags or test `is not None`; `Decimal("0.00")` is a real bound.

- [x] **M4 — Preserve filters safely in pagination** fixed — all four list views normalize boolean aliases to their displayed values and every pagination link URL-encodes every active filter.
  - Source: frontend F-M4
  - URL-encode all values, preserve every active filter, and normalize accepted status aliases to the displayed option.

- [x] **M5 — Distinguish filtered-empty from tenant-empty states** fixed — each list exposes a reset path for filtered-empty results, and WBS cloning is visibly disabled with an explanation when the template has no structure.
  - Source: frontend F-M5
  - All four lists should offer clear-filter recovery; disable WBS cloning when no structure exists.

- [x] **M6 — Use one badge mapping everywhere** fixed — model badge-class properties now drive methodology, complexity, active, scope, field, and team badges across lists, details, and the hub with safe fallbacks.
  - Source: frontend F-M1
  - Hub and entity pages should use model badge properties/shared mappings with safe fallbacks.

- [x] **M7 — Complete required/help/error/accessibility affordances** fixed — checkbox widgets use the real `form-check` class, bound errors render on checkboxes/selects/text fields, the working-day control is a labelled fieldset, and preview/control labels are associated.
  - Sources: frontend F-M2/F-M6
  - Use the real checkbox class, render required/help/errors, associate labels/controls, and use semantic checkbox-group markup.

- [x] **M8 — Eliminate invented currency/timezone defaults** fixed — budget display resolves the core workspace currency, and locale list/detail fall back to the actual core profile or `Not configured`; no `$`, USD, or UTC literals remain in 7.19 templates.
  - Sources: explorer M2, frontend F-M9
  - `ProjectTemplate.target_budget` and locale null states must resolve a real currency/locale or show “Not configured”; do not hardcode `$`, UTC, or USD.

- [x] **M9 — Render recommended role keys as human labels** fixed — template detail maps stored role keys through `ProjectTeamMember.ROLE_CHOICES` and preserves unknown keys as readable fallbacks.
  - Source: frontend F-M10
  - Seed display labels or map known `ProjectTeamMember.ROLE_CHOICES` keys.

- [x] **M10 — Parse integer filters with a bounded decimal helper** fixed — all 7.19 integer FK filters use `as_db_int` plus positive-pk checks; Unicode and oversized values return 200 without database conversion errors.
  - Source: security S-M1
  - Unicode/oversized values currently pass `isdigit()` and then raise on `int()`. Reuse `apps.core.crud.as_db_int` or equivalent ASCII/length/range validation.

- [x] **M11 — Convert JSON recursion/size failures to form errors** fixed — template and custom-field JSON inputs use `strip=False`, pre-parse byte caps, recursion/depth guards, and model-save revalidation; oversized and deeply nested custom-field inputs stayed field errors.
  - Source: security S-M2
  - Catch `RecursionError`, cap raw input size, and keep JSON errors on their fields.

- [x] **M12 — Add the established newest-first tenant indexes** fixed — generated `0029_alter_projecttemplate_estimated_duration_days_and_more.py` adds only the 7.19 `ProjectTeam` and `ProjectTemplate` `(tenant, -created_at)` indexes plus the honest duration help-text alteration.
  - Source: performance P5
  - ProjectTemplate and ProjectTeam need named `(tenant, -created_at)` indexes through a new migration; never edit applied 0028.

- [x] **M13 — Paginate large team membership and bound form option payloads** fixed — current and historical memberships have independent 25-row pages, team/org selectors are bounded and `.only()`-limited, and member selectors are capped at 100 users.
  - Sources: performance P6/P7, frontend F-M8
  - Paginate current/historical members, use `only()` for selector rows, and introduce a searchable/limited selector only if required by the existing app pattern.

- [x] **M14 — Use logical direction utilities** fixed — 7.19 WBS/action spacing and alignment use `ms-*`, `me-*`, and `text-end`; no `ml-*`, `mr-*`, or `text-right` remain in the owned templates.
  - Source: frontend F-M7
  - Replace WBS/action `ml/mr/text-right` layout utilities with logical equivalents where the CDN supports them.

## Refuted / already-green observations

- The alleged migration-help-text drift is **refuted**: `manage.py makemigrations projects --dry-run --check` reported no changes after the current model edits.
- Sequential duplicate membership is rejected visibly; only the concurrent DB race remains.
- Tenant-bound object/child IDOR and crafted foreign-FK POSTs passed independent probes.
- Static confirm messages removed the earlier stored-XSS pattern; no current `|safe`, `mark_safe`, autoescape bypass, or user-controlled inline JS was found.
- WBS GET/POST, positive filters, page 2, inactive-template refusal, empty states, and CSRF/method ordering passed the initial 182-assertion smoke gate.
- The 13-query hub, grouped member counts, and WBS transaction volume are quality findings, not authorization bypasses.

## Fixer completion contract

- [x] Every item above is marked `[x] fixed` or `[~] skipped — reason`.
- [x] `manage.py check` is clean.
- [x] `makemigrations projects --dry-run --check` reports no uncommitted model drift; any necessary new migration is present and applied.
- [x] A fresh runtime probe covers all previously reproduced failures and reports exact denominators with no DB debris.
- [x] No unrelated concurrent file was edited or staged.
