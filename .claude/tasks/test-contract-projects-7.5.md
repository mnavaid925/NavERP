# Test contract — Projects 7.5 Risk & Issue Management

Frozen by Phase 6 step 1. The four test files below consume ONLY the fixtures in
`apps/projects/tests/conftest.py` (generic shared fixtures + the `risk` block) and assert only
names that exist at HEAD. Build order is mandatory: models → forms → views → security.
Every test function is `test_risk_*`; every module-level helper is `_risk_*`.

Build contract of record: `.claude/tasks/contract-projects-7.5.md` (§2 models, §3 forms,
§4 view context keys, §5 templates). Review burn-down of record:
`.claude/tasks/review-projects-7.5.md` — the tests encode the FIXED behaviours
(I1, I4, I5, I9, I10, M4, M9, M13).

## 0. Shared facts (verified against HEAD)

- Models: `projects.ProjectRisk` [RSK-], `projects.RiskResponseAction` [RRA-],
  `projects.ProjectIssue` [ISS-], `projects.IssueEscalation` [ESC-] — all `TenantNumbered`
  (numbers minted in `save()`, never `bulk_create`), all tenant-scoped.
- Band vocabulary (derived, never stored): `severity_band` ∈ `low`/`medium`/`high`/`critical`
  from `probability × impact` via `ProjectRisk.SEVERITY_BANDS`; labels in `ProjectRisk._BAND_LABELS`.
- URL names (30, namespace `projects:`): `rsk_{list,create,detail,edit,delete,realize,close,reopen}`,
  `rra_{list,create,detail,edit,delete,complete}`, `iss_{list,create,detail,edit,delete,escalate,resolve,close}`,
  `esc_{list,create,detail,edit,delete}`, `risk_analysis`, `risk_monitoring`.
- Admin-gated verbs (403 for a member): `iss_escalate`, `rsk_reopen`, `esc_create`, `esc_edit`,
  `esc_delete` (the I9 fix). All other mutating verbs are `@login_required` + `@require_POST` only.
- Monte Carlo (POST `risk_analysis`): seed reproducible; `iterations` clamped to
  `[MIN_ITERATIONS, MAX_ITERATIONS]`; a valid `?seed=` survives an out-of-range `?iterations=`
  and vice versa (M4); the draw population is `cost_impact > 0`, status not realized/closed,
  **id-ascending** (M9).
- Computed-board cap: both boards materialise at most `_REGISTER_CAP = 2000` register rows (M13).

## 1. Fixture inventory (the `risk` conftest block)

Helpers: `_risk_today`, `_risk_project(tenant, **overrides)` (active host project; defaults
merge with overrides), `_risk(tenant, project, **overrides)` (defaults probability=2/impact=2 →
medium, status=identified, cost_impact=0.00), `_risk_action(risk, **overrides)`,
`_risk_issue(tenant, project, **overrides)`, `_risk_escalation(issue, **overrides)`,
`_risk_fill_risks(tenant, project, count)`, `_risk_fill_issues(tenant, project, count)`.

Clients/users: `risk_admin_client` (tenant A admin), `risk_member_client` (tenant A member —
`is_tenant_admin=False`), `risk_csrf_client`, `risk_anon_client`, `risk_tenantless_client`
(superuser, tenant=None → empty results by design); tenant B twins: `risk_b`, `risk_issue_b`,
`risk_action_b`, `risk_escalation_b`, `risk_member_b`.

Rows (tenant A on `risk_project_a` unless noted):
- Bands: `risk_low`, `risk_medium`, `risk_high`, `risk_critical`.
- Lifecycle: `risk_overdue` (review_date = today−3, identified), `risk_realized` (+ its linked
  issue — the I1 invariant), `risk_closed` (lessons_learned set).
- Issues: `risk_issue_open`, `risk_issue_overdue`, `risk_issue_escalated` (escalation_level=2,
  one escalation row), `risk_issue_resolved` (resolution evidence + lessons_learned),
  `risk_issue_closed`.
- Actions: `risk_action_open`, `risk_action_overdue`, `risk_action_completed` (all on
  `risk_high`).
- Simulation set: `risk_sim_project` + `risk_sim_high`, `risk_sim_rare`, `risk_sim_realized`,
  `risk_sim_zero_cost` (population determinism) and `risk_baseline` (7.4 approved+activated
  BudgetRevision for the contingency comparison).

Derived counts in lists depend on which fixtures a test pulls — recompute expectations from the
pulled rows, never from memory.

## 2. `test_risk_models.py`

- Numbering: `save()` mints `RSK-`/`RRA-`/`ISS-`/`ESC-` sequential numbers per tenant; two
  tenants number independently (use `risk_b`).
- Choices: `PROBABILITY_PCT`/`IMPACT`/`STATUS`/category/type/strategy/level vocabularies answer
  their `get_*_display` names.
- Derived properties: `severity_band` at the four band boundaries (score 4/9/14/15+ edges),
  `emv = probability% × cost_impact`, `residual_emv` (None without residual pair), `is_locked`
  False for identified / True for realized+closed; issue `age_days`, `is_overdue` (due_date <
  today while open), escalation `escalated_at` stamp.
- `clean()` guards: a `wbs_node`/`contingency_account` from another project (or another tenant)
  raises `ValidationError` at save (factories run `full_clean()`).
- Meta: `ordering` per model matches the contract; the seven named register indexes exist in
  `Model._meta.indexes` by name — from 0006: `rsk_tnt_created_idx`; from 0008:
  `rsk_tnt_review_idx`, `rsk_tnt_owner_idx`, `rra_tnt_created_idx`, `rra_tnt_strategy_idx`,
  `iss_tnt_type_idx`, `iss_tnt_due_idx`.

## 3. `test_risk_forms.py`

- Six forms: `ProjectRiskForm`, `RiskResponseActionForm`, `ProjectIssueForm`,
  `IssueEscalationForm`, `RiskClosureForm`, `IssueResolutionForm`.
- `Meta.fields`/`exclude`: verb-written fields are OFF every ModelForm (`status`, `number`,
  `tenant`, `closed_at`, `completed_at`, `resolved_at`, `escalation_level`, `escalated_to`,
  `escalated_at`, `created_by` — per form per contract §3).
- FK querysets are tenant-scoped: `form.fields["project"].queryset` excludes foreign-tenant rows
  (build a foreign row via `risk_b` and assert absence).
- `_reject_foreign`: posting a foreign-tenant `project`/`risk`/`issue`/`owner`/`target_user` pk
  fails form validation (no row created).
- Widget classes: `IssueResolutionForm` textareas and `RiskClosureForm` textarea carry
  `form-textarea` (the I5 fix, regression guard).
- `RiskClosureForm` requires `lessons_learned` evidence; `IssueEscalationForm.level` bound to
  `LEVEL_CHOICES` (5 rejected).

## 4. `test_risk_views.py`

- Context keys per contract §4 for every list/detail/form/computed view — the L8 rule: assert
  rendered HTML contains `str(obj)` on each detail page, list page titles, and the pinned
  context keys (`register`, `status_choices`, `projects`, `owners`, `band_choices`, …).
- Lenses: `?band=critical` returns exactly the rows with score 15–25; `?top=1` orders by
  probability/impact/cost; `?overdue=1` ≡ `?review_due=1`; `?escalated=1` narrows the issue log;
  junk enum values fall back to the unfiltered register (no 500, no empty page).
- State machines: realize→issue created atomically (the I1 invariant — realized risk has its
  linked issue); realize twice refused; close only from resolved (issues) / only live→closed
  (risks); reopen only closed (admin only); complete twice refused; escalate refused on
  resolved/closed.
- Monte Carlo: POST same seed twice ⇒ identical percentile figures (strip CSRF tokens before
  comparing); different seed ⇒ different figures; `?iterations=99999` clamps to MAX; valid
  `?seed=` in the query string survives an empty-body POST (M4); zero-population tenant renders
  the honest zero state.
- Monitoring: `?project=` scopes every lens INCLUDING lessons (I10 — no foreign project's issue
  rows); burn-down bars render.
- Cap (M13): a register over `_REGISTER_CAP` rows is not required in tests (too slow) — assert
  the constant exists and both views reference it instead.
- No `{#` or `{% comment` markers leak into any rendered 7.5 page (L3).

## 5. `test_risk_security.py`

- IDOR: for every `<int:pk>` route of all four registers — detail/edit (GET + POST) and every
  POST verb/delete — tenant B's pk for tenant A's client ⇒ 404 (assert on POST too, not just
  the GET 405).
- Admin gates (I9 + existing): member client ⇒ 403 on `iss_escalate`, `rsk_reopen`,
  `esc_create`, `esc_edit`, `esc_delete`; admin client ⇒ 302 success.
- Template gating (I9): the escalation list/detail pages render no Add/Edit/Delete control for
  the member client and do render them for the admin client (assert on HTML presence).
- `@require_POST`: GET on every mutating verb ⇒ 405.
- Anonymous: every GET ⇒ redirect to login; the tenantless superuser ⇒ 200 with empty states.
- CSRF absent ⇒ 403 on one representative POST per register (`risk_csrf_client` counterpart
  without the token).

## 6. Verification per file

Run the new file, then the shared conftest must still import for the whole app:
`venv/Scripts/python.exe -m pytest apps/projects/tests/test_risk_<x>.py -q`.
The FINAL gate is the full unfiltered suite
(`venv/Scripts/python.exe -m pytest apps/projects/tests -q`) — never `-k`-filtered (L47).
