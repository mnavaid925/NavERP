# Review â€” procurement 6.2 Requisition Management

Date: 2026-08-22 Â· Base: e220f522df8a06828c9d42dfc0226c756d8e2dfa Â· Six parallel lanes: code-reviewer Â· frontend-reviewer Â· explorer Â· performance-reviewer Â· qa-smoke-tester Â· security-reviewer

| Lane | Result |
|---|---|
| code-reviewer | C1 Â· I2â€“I5 Â· M6â€“M9 |
| frontend-reviewer | I1â€“I3 Â· M4â€“M7 |
| explorer | I1 Â· M2â€“M5 |
| performance-reviewer | C1 Â· I1â€“I2 Â· M1â€“M4 |
| qa-smoke-tester | PASS â€” 65/65 checks, 2 informational |
| security-reviewer | I1â€“I2 Â· M3â€“M7 |

## Findings (deduped, ID order)

- [x] **C1** views/RequisitionManagement/Requisitions.py:79 â€” `duplicate_pk_set(request.tenant.pk, â€¦)` â†’ AttributeError 500 for the by-design tenant-less superuser; sibling views guard this exact case. Fix: tenant-None guard + redirect dashboard.
- [x] **C2** views/_helpers.py:90â€“97 â€” `_duplicate_maps` scans the ENTIRE live window (all PRs + all their lines) on every call behind req_list/req_detail/template_apply. Fix: bound the candidate set (newest N) so cost is capped.
- [x] **I1** models/â€¦/Amendments.py â€” missing `unique_together = ("tenant", "number")`; number-collision retry in TenantNumbered.save() can never fire. Fix + migration 0004.
- [x] **I2** models/â€¦/Amendments.py:apply_to_requisition â€” vanished target line returns "" and is silently dropped from the applied-summary. Fix: report it.
- [x] **I3** views/â€¦/Amendments.py approve/reject â€” TOCTOU: status checked outside the lock; concurrent decisions can double-apply. Fix: select_for_update() + re-check inside atomic (filing path too).
- [x] **I4** templates/â€¦/requisitions/list.html:67 â€” amendment button gated on scm's `is_editable` (draft/pending) while the view accepts pending/approved â€” wrong statuses both ways. Fix: gate on the amendable pair.
- [x] **I5** templates â€” CRUD affordances missing on register/detail (Edit/Delete deep-links into scm's existing views). Fix: conditional links per CRUD Completeness Rules.
- [x] **I6** forms â€” both line formsets lack `max_num`: crafted TOTAL_FORMS yields ~1100 validated rows/INSERTs. Fix: max_num=50 (template lines) / 25 (amendment rows).
- [x] **I7** (SKILL.md documents the append-only decision trail) amendments have no edit/delete route â€” DELIBERATE (decision trail is append-only); document in SKILL.md rather than add destructive verbs.
- [x] **I8** models/â€¦/Amendments.py:15 â€” first-ever cross-app MODELS-layer import (`from apps.scm.models import â€¦`). Fix: defer into `apply_to_requisition()` like `_helpers.py` does.
- [x] **I9** qa lane â€” build smoke's cancel-filing step was vacuous (posted against a draft); superseded by QA lane's real E2E cancel flow (PASS). No code change needed.

### Minor

- [x] **M1** templates list.html:62 â€” "Possible duplicate" badge links to the row's OWN page; render as non-linked badge instead.
- [x] **M2** detail.html duplicates table hardcodes badge-muted for all statuses; use the standard statusâ†’colour chain.
- [x] **M3** navigation.py comment says ?dupes=1 filters to "flagged rows"; it filters to CHECK CANDIDATES. Reword.
- [x] **M4** admin.py â€” template/amendment admins omit readonly system columns (number/created_by/stamps; amendment status editable bypasses apply()). Add readonly_fields.
- [x] **M5** seeder â€” template/amendment creates not wrapped in transaction.atomic (partial-failure poisons the idempotency guard) and templates write no audit baseline. Wrap + log.
- [x] **M6** forms/RequisitionManagement/__init__.py bare marker â€” add the same justification comment the views sub-package carries.
- [x] **M7** template_apply does not enforce `is_active` server-side (only the button hides). Guard in view.
- [x] **M8** helpers final matched-fetch lacks tenant_id filter (defense-in-depth). Add.
- [x] **M9** views/â€¦/Amendments.py docstring claims "on their requisitions" but any member may file â€” align wording (same-workspace visibility is deliberate).
- [x] **M10** template_detail queries lines twice (property re-fetch). Compute total from the already-fetched list.
- [x] **M11** amendments/form.html â€” proposed-header fields stay visible under Cancel though they'd error. Add inline note tying them to Amend type.
- [x] **M12** perf â€” `.only()` trimming on list payloads / composite index â€” SKIPPED: negligible at this app's scale; FK indexes already cover the hot filters (verified by perf lane).
- [x] **M13** qa â€” hand-built clients omitting extra-row keys get validation errors instead of graceful skip â€” SKIPPED: identical to shipped SCM 4.1 behaviour; browsers unaffected.
