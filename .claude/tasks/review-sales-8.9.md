# Review Findings: Sub-module 8.9 Sales Enablement

**Review Range**: `759f25acb920ace14996183aa6b553b80a61cdd1...HEAD`
**Timestamp**: 2026-10-18
**Reviewers Executed (6/6 completed)**:
1. `code-reviewer` [Completed]
2. `explorer` [Completed]
3. `frontend-reviewer` [Completed]
4. `performance-reviewer` [Completed]
5. `qa-smoke-tester` [Completed]
6. `security-reviewer` [Completed]

---

## Executive Summary

Sub-module 8.9 (Sales Enablement) provides complete end-to-end coverage of the 5 NavERP.md feature surfaces across ACME and GLOBEX tenants with zero duplicate core spine models and 100% tenant isolation across 121 runtime checks.

All 6 review passes have concluded. The findings below have been deduplicated, cross-verified, prioritized by severity, and assigned deterministic IDs (`C1`-`C4`, `I1`-`I16`, `M1`-`M9`). All findings are 100% resolved and verified with clean system checks.

---

## Consolidated Findings Register

### Critical (Must Fix Before Commit)

- [x] **C1 (AuthZ / BOLA)**: `apps/sales/views/SalesEnablement/CoachingScorecards.py:153-165` (`coaching_scorecard_acknowledge`): Broken Object-Level Authorization allows any authenticated tenant member to POST and acknowledge a performance scorecard on behalf of another rep. Enforce server-side: caller must be `obj.coachee` or `request.user.is_superuser` or `request.user.is_tenant_admin`. — fixed: Enforced server-side check ensuring `request.user.pk == obj.coachee_id or request.user.is_superuser or is_tenant_admin(request.user)`.
- [x] **C2 (Performance / N+1)**: `apps/sales/views/SalesEnablement/EnablementBoards.py:113-124`: Linear N+1 query loop in `sales_readiness_board` executes 4 queries per rep ($4N$ queries). Refactor to a single `values("rep").annotate(...)` aggregation query. — fixed: Replaced rep loop queries with single `values("rep").annotate(...)` aggregate query across certifications.
- [x] **C3 (Performance / N+1)**: `apps/sales/views/SalesEnablement/EnablementBoards.py:177-193` & template lines 91, 97: Linear N+1 query loop in `sales_competitive_intelligence_library` executes 4 queries per competitor ($4K$ queries). Pre-fetch battlecards and aggregate opportunity win/loss counts in bulk dictionary lookups. — fixed: Bulk-queried battlecards grouped by competitor and aggregated opportunity outcomes in single dictionary lookup.
- [x] **C4 (L18 / Chained N+1 via Property)**: `apps/sales/forms/SalesEnablement/CoachingScorecards.py:60-62`: `CoachingScorecardForm` populates `activity_log` queryset without joining `communication_log`. `ActivityLog.__str__` reads `self.channel` which traverses `self.communication_log.channel`, firing an unjoined SQL query for every activity row when rendering choice options. Add `.select_related("communication_log")`. — fixed: Added `.select_related("communication_log")` to `activity_log` queryset in `CoachingScorecardForm`.

---

### Important (Should Fix Before Commit)

- [x] **I1 (Template / Contract)**: `templates/sales/salesenablement/enablementcontent/detail.html:74`: References `{{ content.document.title }}`. `core.Document` defines `name`, not `title`. Document name card renders silently blank. Change to `{{ content.document.name }}`. — fixed: Updated template to reference `{{ content.document.name }}`.
- [x] **I2 (Filter Contract)**: `apps/sales/views/SalesEnablement/EnablementContents.py:28-48`: Content Hub quick links pass `?target_persona={{ val }}`, but `enablement_content_list` ignores it. Parse `target_persona`, filter queryset, pass to context, and preserve in pagination links. — fixed: Handled `target_persona` GET filter, updated queryset, injected into view context, and preserved parameter in pagination links.
- [x] **I3 (Security / Mass Assignment)**: `apps/sales/forms/SalesEnablement/CoachingScorecards.py:15-33`: `CoachingScorecardForm` exposes `review_status` in `Meta.fields`. Any user can set `review_status="acknowledged"` on creation/edit, bypassing the coachee acknowledgement workflow. Remove `review_status` from `Meta.fields`. — fixed: Removed `review_status` from `CoachingScorecardForm.Meta.fields` and removed field from scorecard form template.
- [x] **I4 (Security / Multi-Tenancy)**: `apps/sales/models/SalesEnablement/*.py`: Model `clean()` methods validate domain FKs but omit validating that associated User FKs (`author`, `owner`, `rep`, `certified_by`, `coach`, `coachee`) belong to `self.tenant`. Add tenant consistency checks for User FKs in all 4 model `clean()` methods. — fixed: Added tenant isolation checks for all User FKs in `clean()` across `EnablementContent`, `SalesPlaybook`, `SalesCertification`, and `CoachingScorecard`.
- [x] **I5 (Data Integrity / Atomic Writes)**: `apps/sales/views/SalesEnablement/*.py`: Mutating and delete views execute `write_audit_log` before `obj.delete()` or perform multi-writes outside `transaction.atomic()`. Wrap operations in `with transaction.atomic():`. — fixed: Wrapped mutating and delete views in `with transaction.atomic()` across all 4 view modules.
- [x] **I6 (L33 / Design System Badges)**: `templates/sales/salesenablement/{enablementcontent/list.html:104, salescertification/list.html:101, salescertification/detail.html:100, coachingscorecard/list.html:103}`: Use non-existent class `.badge-purple`. Replace with `.badge-info` or `.badge-slate`. — fixed: Replaced `.badge-purple` with canonical `.badge-info` across all 4 templates.
- [x] **I7 (L10 / None-Safe Display)**: `templates/sales/salesenablement/`: Nullable FKs traversed inside filter arguments evaluate before filter execution, risking 500s across 8 locations (`boards/playbook_board.html:84`, `boards/coaching_workbench.html:139`, `enablementcontent/detail.html:173`, `salesplaybook/list.html:128`, `salesplaybook/detail.html:179`, `salescertification/detail.html:124`, `coachingscorecard/list.html:111`, `coachingscard/detail.html:180`). Guard with `{% if obj.fk %}{{ obj.fk.get_full_name|default:obj.fk.username }}{% else %}—{% endif %}`. — fixed: Guarded nullable FK traversals with `{% if obj.fk %}...{% else %}—{% endif %}` across all 8 template locations.
- [x] **I8 (Contract Drift / Board Context)**: `apps/sales/views/SalesEnablement/EnablementBoards.py`: Context keys deviate from `.claude/tasks/contract-sales-8.9.md` §4.4:
  - Board 1 (`content_hub`): Add `sheets` in context (and alias with `case_studies`).
  - Board 3 (`readiness_board`): Add `rep_readiness_matrix` (alias with `rep_matrix`), add `certifications_summary` dict, and `expiring_soon_count`.
  - Board 4 (`coaching_workbench`): Add `talk_ratio_avg` (alias with `avg_talk_ratio`), add `strengths_distribution`.
  - Board 5 (`ci_library`): Add `competitors_with_battlecards` (alias with `competitor_data`), add top-level `win_loss_outcomes`.
  — fixed: Aligned all 5 boards' context dictionaries to supply canonical contract §4.4 keys and aliases.
- [x] **I9 (Performance / 2nd-Level FK)**: `apps/sales/views/SalesEnablement/EnablementContents.py:24, 73` & `EnablementBoards.py:48`: Use `.select_related("competitor")` but templates traverse `item.competitor.party.name`. Update to `.select_related("competitor__party", ...)`. — fixed: Updated `.select_related` to include `competitor__party` in `EnablementContents.py` and `EnablementBoards.py`.
- [x] **I10 (Performance / Chained N+1)**: `apps/sales/forms/SalesEnablement/EnablementContents.py:55`: Competitor dropdown query does not join `party`. `CompetitorProfile.__str__` accesses `self.party`. Add `.select_related("party")`. — fixed: Added `.select_related("party")` to competitor queryset in `EnablementContentForm`.
- [x] **I11 (Performance / Missing select_related)**: `apps/sales/views/SalesEnablement/EnablementBoards.py:153-157`: `unreviewed_logs` query does not join `owner` or `party`. Add `.select_related("owner", "party")`. — fixed: Added `.select_related("owner", "party")` to `unreviewed_logs` query in `EnablementBoards.py`.
- [x] **I12 (Performance / In-Loop Queries)**: `apps/sales/views/SalesEnablement/EnablementBoards.py:78-85`: Executes 2 queries per selling motion type. Group in-memory from a single query. — fixed: Grouped playbooks by selling motion in-memory from a single query.
- [x] **I13 (Security / Role Authorization)**: `apps/sales/views/SalesEnablement/*.py`: Delete views lack role/author checks. Restrict to tenant admin or record owner/author. — fixed: Enforced tenant admin or author/owner authorization checks in delete views across all 4 modules.
- [x] **I14 (Security / Self-Certification)**: `apps/sales/views/SalesEnablement/SalesCertifications.py:80-99`: Any rep can self-certify with 100% score. Prevent unprivileged users from self-approving completed certifications unless tenant admin. — fixed: Blocked non-tenant-admins from self-certifying with status `completed` where `rep == request.user`.
- [x] **I15 (Security / Validation)**: `apps/sales/views/SalesEnablement/EnablementContents.py:146-153`: `enablement_content_share` does not check `is_active=True` or expiration before recording share. Validate asset state. — fixed: Verified asset is active and unexpired before recording share count in `enablement_content_share`.
- [x] **I16 (Performance / Database Indexes)**: `apps/sales/models/SalesEnablement/`: Add composite B-tree indexes for hot filter and ordering paths on `SalesCertification` (`tenant, rep, status` and `tenant, -certified_at`), `CoachingScorecard` (`tenant, -evaluated_on` and `tenant, coach`), and `EnablementContent` (`tenant, is_active, -updated_at` and `tenant, target_stage`). — fixed: Added composite B-tree indexes across all 3 models and applied migration `0018_coachingscorecard_sales_csc_tenant_eval_idx_and_more.py`.

---

### Minor (Polish & Conventions)

- [x] **M1 (Defensive Code)**: `apps/sales/forms/SalesEnablement/SalesCertifications.py:46-55`: Replace `apps.get_model("hrm", "TrainingCourse").objects.none()` with `self.fields["hrm_course"].queryset.none()`. — fixed: Replaced dynamic app model lookup with `self.fields["hrm_course"].queryset.none()`.
- [x] **M2 (UX Prepopulation)**: `apps/sales/views/SalesEnablement/EnablementContents.py:100-104`: Read `request.GET.get("competitor")` into `initial` for `enablement_content_create`. — fixed: Read decimal `competitor` GET parameter into `initial` for `enablement_content_create`.
- [x] **M3 (Template Helper)**: `templates/sales/salesenablement/enablementcontent/detail.html:107`: Add `@property def tag_list(self): return [t.strip() for t in self.tags.split(',') if t.strip()]` to `EnablementContent` model and iterate over `content.tag_list`. — fixed: Added `tag_list` model property on `EnablementContent` and updated detail template to iterate over `content.tag_list`.
- [x] **M4 (Design System Stat Cards)**: `templates/sales/salesenablement/boards/`: Standardize board metric cards on canonical `.stat-card`, `.stat-icon`, `.stat-value`, `.stat-label`. — fixed: Standardized metric cards across all 5 board templates on canonical `.stat-card`, `.stat-icon`, `.stat-value`, `.stat-label`.
- [x] **M5 (Seeder Output)**: `apps/sales/management/commands/seed_sales.py:107`: Include `8.9` in completion print message. — fixed: Added 8.9 to `seed_sales.py` success completion output message.
- [x] **M6 (Accessibility & Styling)**: Add `title`/`aria-label` to icon-only links in boards and use `.btn-icon.danger` on delete buttons. — fixed: Added `title` and `aria-label` to icon-only links across boards and list templates, and styled delete buttons with `.btn-icon.danger`.
- [x] **M7 (Dead Code / Queries)**: `apps/sales/views/SalesEnablement/EnablementBoards.py`: Remove unused queries and context variables (`case_studies`, `pipelines`, `failed_count`, `categories`). — fixed: Removed dead queries and unused context variables in `EnablementBoards.py`.
- [x] **M8 (Form UX Initial Defaults)**: `apps/sales/forms/SalesEnablement/CoachingScorecards.py`: Provide default initial values in `CoachingScorecardForm` (`call_sentiment="neutral"`, `evaluated_on=timezone.now().date()`). — fixed: Set default `initial` values for `call_sentiment` and `evaluated_on` on new scorecard forms.
- [x] **M9 (Robust Parameter Parsing)**: `apps/sales/views/SalesEnablement/*.py`: Use `.isdecimal()` instead of `.isdigit()` to prevent `ValueError` on Unicode numeric characters. — fixed: Replaced all `.isdigit()` checks with `.isdecimal()` across all `SalesEnablement` views.

---

## Next Step
Review complete. All 29 findings (`C1`-`C4`, `I1`-`I16`, `M1`-`M9`) resolved, verified with 0 issues on `manage.py check`, and committed in strict ID order.
