# Review — procurement 6.1 User Dashboard & Portal (2026-08-21)

Changeset reviewed against BASE `32bdaaf32b183ce2aba2ab3d060506e71698ac34`. Lanes run:
code-reviewer, performance-reviewer, qa-smoke-tester, security-reviewer (in-session — two subagent
returns for this lane came back empty, so the checklist was completed directly; explorer and
frontend-reviewer folded into the code lane since a single agent covered both surfaces).

| Lane | Verdict | Findings |
|---|---|---|
| Code review | Ship after fixes | CR-1..CR-8 |
| Performance | Clean | PF-1..PF-3 (all Minor) |
| QA smoke | PASS 6/6 | none (naive-datetime warnings are scm-seeder fixtures, pre-existing) |
| Security | Protected; no Critical/High | SE notes below |

## Findings

- **CR-1 · Important · ProcurementAlerts model `clean()`** — `link_url` guard rejects `//evil.com`
  but accepts `/\evil.com`; browsers canonicalize `\` to `/`, making it protocol-relative → open
  redirect. Fix: reject any backslash.
- **CR-2 · Important · `resolve()` / `alert_resolve` view** — resolving an already-resolved alert
  re-stamps who/when/note (unlike `acknowledge()`, which early-returns). Fix: early-return +
  info message.
- **CR-3 · Minor · forms/_common.py `_active_currencies`** — dead code in this app. Remove.
- **CR-4 · Minor · Overview `my_open_alerts_list`** — nullable `due_at` ordering puts NULLs first
  on MariaDB. Fix: `.asc(nulls_last=True)` (Django 5.1 emulates on MariaDB — verified in compiler
  source).
- **CR-5 · Minor · QuickRequisitionForm quantity/unit price** — no upper bound vs
  `Decimal(14,x)` columns → driver DataError 500 on huge values. Fix: MaxValueValidator ceilings.
- **CR-6 · Minor · WidgetPreference.save_choices** — bare update_or_create loop can race the
  unique_together. Fix: wrap in transaction.atomic().
- **CR-7 · Minor · widget save not audited** — deliberate: personal layout preference, not
  business data; auditing would spam the feed the module itself renders. Documented instead.
- **CR-8 · Minor · "Committed this month" wording** — filter is raised-this-month AND now
  committed, not approved-in-month. Reword labels/comment honestly.
- **PF-1 · Minor** — `hidden_keys()` computed twice per overview GET. Hoist once.
- **PF-2 · Minor** — `severity` list filter unindexed. Add `(tenant, severity)` index + migration.
- **PF-3 · Minor** — unused select_related JOINs on `my_open_alerts_list`/`due_requisitions`.
  Drop.
- **PF clean-list**: all template FK dereferences select_related-covered (alert list/detail,
  overview widgets, feed pages); trend = one TruncMonth GROUP BY; Case-annotation ordering does
  not poison Paginator.count; every surface paginated or SQL-sliced; AuditLog OR-filter rides the
  `(tenant, at)` index with LIMIT-ed page reads — acceptable at scale.

## Security checklist (in-session)

- Tenant scoping: every get_object_or_404 carries `tenant=request.tenant` (list/detail/edit/
  delete/acknowledge/resolve/activity_detail) ✓; cross-tenant detail → 404 verified by smoke ✓.
- activity_detail restricted to the procurement domain queryset, not arbitrary audit rows ✓.
- Lifecycle actions POST-only (`@require_POST`), delete POST-only + confirm + csrf ✓; widget
  toggle POST + `{% csrf_token %}` ✓; anonymous → login redirect (QA step 5) ✓.
- quickreq_create: requester hardwired to request.user, estimated_total derived server-side via
  recalc_totals(), header+line atomic ✓.
- Forms: QuickRequisitionForm scopes gl_account/org_unit manually; currency limited to active;
  ProcurementAlertForm assigned_to auto-scoped by TenantModelForm (User carries tenant field —
  verified apps/core/forms/_common.py:52-55) plus `_reject_foreign` crafted-POST re-check ✓.
- CSV export: `_csv_safe` neutralizes formula injection on user-controlled cells; filename fixed,
  no header injection ✓.
- link_url rendered as href only; internal-path invariant enforced in clean() (CR-1 closes the
  backslash hole).
- AuditLog.changes for procurement objects contains only non-sensitive fields via upstream
  `_SENSITIVE_AUDIT_FIELDS` redaction (apps/core/crud.py); no secrets logged anywhere ✓.

## Disposition

Fix CR-1..CR-6, PF-1..PF-3 in ID order; CR-7 documented-not-coded; CR-8 wording fix. Re-run smoke
after fixing.
