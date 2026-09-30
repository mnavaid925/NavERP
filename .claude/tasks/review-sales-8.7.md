# Review Findings: Sales 8.7 Territory & Quota Management

Review of `02d8aa79...HEAD` across all 6 review passes:
- Pass 1: `code-reviewer`
- Pass 2: `explorer`
- Pass 3: `frontend-reviewer`
- Pass 4: `performance-reviewer`
- Pass 5: `qa-smoke-tester`
- Pass 6: `security-reviewer`

---

## Critical

### [x] fixed — [C1] HTTP 500 on Account Territory Assignment Edit POST (`AttributeError: save_m2m`) & Stamped Audit Field Overwrite
<!-- commit: fix(sales): delegate account territory assignment edit to crud_edit (C1) -->
- **Location:** `apps/sales/views/TerritoryQuotaManagement/AccountTerritoryAssignments.py:204-219`
- **Description:** In `account_territory_assignment_edit`, the view manually assigns fields on `locked` instead of delegating to `form.save(commit=False)`. Calling `form.save_m2m()` at line 215 crashes with `AttributeError: 'AccountTerritoryAssignmentForm' object has no attribute 'save_m2m'` because `save_m2m` is only bound to `ModelForm` when `form.save()` is executed. Additionally, line 213 executes `locked.assigned_by = request.user`, overwriting immutable origin evidence stamped at creation.
- **Fix:** Refactor `account_territory_assignment_edit` to delegate to `crud_edit(request, model=AccountTerritoryAssignment, pk=pk, form_class=AccountTerritoryAssignmentForm, template=FORM_TEMPLATE, success_url=reverse("sales:account_territory_assignment_detail", args=[pk]), extra_context=_form_context(request))` matching sibling entities, preserving `assigned_by` immutability and eliminating the 500.

### [x] fixed — [C2] Foreign Key Display Crash in `territory_performance` Board
<!-- commit: fix(sales): fix foreign key reporting currency display in territory performance board (C2) -->
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:724`
- **Description:** Line 724 executes `period.get_reporting_currency_display()`. `ForecastPeriod.reporting_currency` is a ForeignKey to `accounting.Currency`, not a choice field. Calling `get_FIELD_display()` raises `AttributeError: 'ForecastPeriod' object has no attribute 'get_reporting_currency_display'`, crashing the territory performance board whenever deal currencies differ from reporting currency.
- **Fix:** Change `period.get_reporting_currency_display()` to `(period.reporting_currency.code if period.reporting_currency else "—")`.

### [x] fixed — [C3] Invalid Rule Condition Operator `"equals"` in `seed_sales.py`
<!-- commit: fix(sales): use valid operator eq instead of equals in seeded territory rules (C3) -->
- **Location:** `apps/sales/management/commands/seed_sales.py:1429, 1446`
- **Description:** Seeded rules `rule_geo` and `rule_size` define conditions using `"operator": "equals"`. However, `ROUTING_OPERATORS` in `TerritoryRules.py:44-54` only permits `"eq"`, `"ne"`, `"gt"`, `"gte"`, `"lt"`, `"lte"`, `"in"`, `"not_in"`, `"contains"`. This causes `_condition_matches` to fail to recognize `"equals"`, silently returning `False` for all evaluated accounts, and any clean/save triggers `ValidationError: Unsupported territory operator: equals`.
- **Fix:** Change `"operator": "equals"` to `"operator": "eq"` at lines 1429 and 1446 in `seed_sales.py`.

### [x] fixed — [C4] Broken Split Sum Validation in `TerritoryMember._check_split_sums`
<!-- commit: fix(sales): correct direct split sum validation for shared territories (C4) -->
- **Location:** `apps/sales/models/TerritoryQuotaManagement/TerritoryMembers.py:164-185`
- **Description:** 
  1. `if not siblings.filter(assignment_type="shared").exists(): return` exits early without validating direct splits when creating the very first shared member on a territory.
  2. `total = sum(...) + (self.coverage_split_pct or Decimal("0"))` adds `self.coverage_split_pct` even when `self.assignment_type != "direct"`. If a territory has 100% direct split coverage and an admin adds an overlay specialist or a shared rep, `total` becomes 100 + split (e.g. 120%), raising a false `ValidationError` and blocking valid overlay/shared assignments.
- **Fix:** Update check:
  ```python
  is_shared_territory = (self.assignment_type == "shared") or siblings.filter(assignment_type="shared").exists()
  if not is_shared_territory:
      return
  direct_self = (self.coverage_split_pct or Decimal("0")) if self.assignment_type == "direct" else Decimal("0")
  total = sum((row.coverage_split_pct or Decimal("0")) for row in siblings if row.assignment_type == "direct") + direct_self
  ```

### [x] fixed — [C5] Truthy Evaluation of `None` in `TerritoryMember._paired_user_is_ae`
<!-- commit: fix(sales): fix truthy evaluation of None in paired AE validation (C5) -->
- **Location:** `apps/sales/models/TerritoryQuotaManagement/TerritoryMembers.py:131, 146-155`
- **Description:** `_paired_user_is_ae()` returns `None` when pairing cannot be judged. Line 131 uses `if self.paired_user_id and not self._paired_user_is_ae():`. In Python, `not None` evaluates to `True`, triggering a spurious `"A pairing must point at a member whose role is Account Executive."` validation error when the paired user cannot be found or is cross-tenant.
- **Fix:** Change line 131 to `if self.paired_user_id and self._paired_user_is_ae() is False:`, and query `.filter(tenant_id=self.tenant_id, territory_id=self.territory_id, user_id=self.paired_user_id, member_role="ae").exists()`.

### [x] fixed — [C6] Quota Plan Workflow Bypass: Submitted Plans Editable and Rejected Plans Deadlocked
<!-- commit: fix(sales): guard quota plan edit on submitted status and allow resubmit for rejected plans (C6) -->
- **Location:** `apps/sales/views/TerritoryQuotaManagement/QuotaPlans.py:243-286`, `apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py:76-77`
- **Description:**
  1. Plans awaiting approval (`status == "submitted"`) are not listed in `FROZEN_STATES = {"approved", "locked"}` and are editable in `quota_plan_edit`, allowing growth targets and parameters to be altered while in the admin queue without approval reset.
  2. When an admin rejects a plan, `status` becomes `"rejected"`. `quota_plan_submit` checks `if obj.status != "draft":`, refusing submission. Because `status` is excluded from the form, editing a rejected plan leaves status as `"rejected"`, bricking the plan permanently.
- **Fix:**
  - Guard `quota_plan_edit`: disallow editing plans with status `"submitted"`, `"approved"`, or `"locked"`.
  - When saving an edit on a `"rejected"` plan, reset its status to `"draft"`.
  - In `quota_plan_submit`, allow submission if `obj.status in ("draft", "rejected")`.

### [x] fixed — [C7] In-Memory Post-Slice Filtering in Territory Boards Truncating Records
<!-- commit: fix(sales): filter accounts at database level before slicing in territory white space board (C7) -->
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:860-932`
- **Description:** `accounts = list(accounts_qs[:MAX_BOARD_ACCOUNTS])` slices the accounts first, and then in-memory loops apply coverage/tier/industry filtering. If the first `MAX_BOARD_ACCOUNTS` accounts do not match the filter, the board displays zero rows even when matching accounts exist beyond the slice.
- **Fix:** Apply tier and industry filters directly to `accounts_qs` at the database level before applying `[:MAX_BOARD_ACCOUNTS]`.

---

## Important

### [x] fixed — [I1] Unfiltered Foreign Key Dropdowns in Model Forms (Tenant Isolation Guard)
<!-- commit: fix(sales): filter foreign keys by tenant across territory quota model forms (I1) -->
- **Location:** `apps/sales/forms/TerritoryQuotaManagement/TerritoryMembers.py:84-93`, `QuotaPlans.py:114-128`, `AccountTerritoryAssignments.py:81-103`
- **Description:** `TerritoryMemberForm` fails to filter `self.fields["territory"].queryset`. `QuotaPlanForm` fails to filter `territory` and `owner` querysets and does not clear them when `self.tenant is None`. `AccountTerritoryAssignmentForm` leaves `owner` unfiltered when `self.tenant is None`.
- **Fix:** Filter all FK querysets to `request.tenant` (and active status where applicable), and explicitly assign `.none()` to all FK fields when `self.tenant is None`.

### [x] fixed — [I2] Broken Condition Value Rendering in `territoryrule/detail.html` via `|join:", "` on Scalars
<!-- commit: fix(sales): render scalar condition values without join in territory rule detail (I2) -->
- **Location:** `templates/sales/territoryquotamanagement/territoryrule/detail.html:91`
- **Description:** Line 91 applies `|join:", "` unconditionally to `condition.value`. In `TerritoryRule.conditions`, `condition["value"]` is only a list for `in` and `not_in` operators; for all other operators it is a scalar. Applying `|join:", "` iterates strings character-by-character (e.g. `"Enterprise"` renders as `"E, n, t, e, r, p, r, i, s, e"`).
- **Fix:** Check `{% elif condition.operator == "in" or condition.operator == "not_in" %}{{ condition.value|join:", " }}{% else %}{{ condition.value }}{% endif %}`.

### [x] fixed — [I3] Unapproved `stat-icon red` Across 8 Templates (Design System Violation)
<!-- commit: fix(sales): replace unapproved stat-icon red with orange across 8 templates (I3) -->
- **Location:** `accountterritoryassignment/detail.html:32`, `accountterritoryassignment/list.html:33`, `coverage_gap.html:52,55`, `rebalance_preview.html:52`, `white_space.html:53`, `quotaplan/detail.html:38`, `territorymember/list.html:34`
- **Description:** Under the NavERP design system (L33), stat icon colors are strictly limited to `blue`, `green`, `orange`, `purple`, and `slate`. `red` is unstyled.
- **Fix:** Replace `red` with `orange` across all 8 stat-card declarations.

### [x] fixed — [I4] Coverage Gap Board Falsely Flags All Non-SDR Members as Orphaned SDR Pairings
<!-- commit: fix(sales): filter orphaned pairings to SDR role only in coverage gap board (I4) -->
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:562-566`
- **Description:** `orphaned_pair_rows` query in `territory_coverage_gap` is missing `.filter(member_role="sdr")`. Without this filter, every active Hunter, Farmer, AE, Overlay Specialist, and Sales Engineer with `paired_user=None` is displayed in the "SDR pairings with no active account executive" table.
- **Fix:** Add `.filter(member_role="sdr")` to `orphaned_pair_rows` in `TerritoryBoards.py:563`.

### [x] fixed — [I5] In-Loop `select_for_update` in `territory_rule_run`
<!-- commit: perf(sales): batch prefetch and lock assignments in territory rule run (I5) -->
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryRules.py:246-281`
- **Description:** For each diff entry, `territory_rule_run` issues a separate `select_for_update` on `AccountTerritoryAssignment` inside the loop, creating serial row locks and latency.
- **Fix:** Prefetch and lock candidate assignments in batch or streamline assignment deactivations.

### [x] fixed — [I6] Subquery Optimization in `territory_performance` Board
<!-- commit: perf(sales): use assignment account subquery in territory performance board (I6) -->
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:663-712`
- **Description:** `territory_performance` extracts all assignment IDs into a Python list and issues `party_id__in=assignment_account_ids` queries over deals and orders. On large tenants, this can exceed SQL parameter limits.
- **Fix:** Use subquery `party_id__in=AccountTerritoryAssignment.objects.filter(...).values('account_id')` directly in the query.

### [x] fixed — [I7] Redundant Duplicate Queries on `AccountProfile` and `AccountClassification` Across Boards
<!-- commit: perf(sales): eliminate redundant duplicate account profile and classification queries across territory boards (I7) -->
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:138-147, 298-307, 423-432, 514-521`
- **Description:** Helper functions `_build_account_profile_map` and `_build_account_classification_map` are invoked repeatedly across helper routines, creating duplicated queries for the same account IDs.
- **Fix:** Pass cached/precomputed profile and classification maps through board helper functions.

### [x] fixed — [I8] Invariant Guard on Subtree Primary Rules in `TerritoryRule.clean()`
<!-- commit: fix(sales): forbid primary alignment on subtree territory rules (I8) -->
- **Location:** `apps/sales/models/TerritoryQuotaManagement/TerritoryRules.py:120-140`
- **Description:** When a rule has `assignment_scope="subtree"` and `alignment_type="primary"`, automated assignment execution can create multiple active primary assignments for the same account across the hierarchy.
- **Fix:** In `TerritoryRule.clean()`, forbid `alignment_type == "primary"` when `assignment_scope == "subtree"`.

### [x] fixed — [I9] Potential Unhandled `DoesNotExist` in `QuotaPlan.clean()`
<!-- commit: fix(sales): guard DoesNotExist when validating foreign keys in QuotaPlan.clean (I9) -->
- **Location:** `apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py:178, 184`
- **Description:** `self.quota_ref` and `self.forecast_period` are dereferenced directly in `clean()`. If foreign keys failed tenant validation, accessing them raises `crm.SalesQuota.DoesNotExist` instead of collecting clean validation errors.
- **Fix:** Skip direct attribute access when foreign keys failed tenant validation.

### [I10] Model-Level Frozen State Check in `QuotaPlan.clean()`
- **Location:** `apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py:167-204`
- **Description:** While views guard frozen status, `QuotaPlan.clean()` does not enforce immutability of plans in `FROZEN_STATES` at the model level.
- **Fix:** In `QuotaPlan.clean()`, check if `self.pk` and DB status is in `FROZEN_STATES`, and raise `ValidationError`.

### [I11] Missing Server-Side Lifecycle Guard in `territory_member_edit`
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryMembers.py:158-169`
- **Description:** While the detail template hides the edit button for ended memberships (`effective_to < timezone.localdate()`), `territory_member_edit` lacks a server-side check, allowing direct POST edits to historical roster records.
- **Fix:** Add server-side check: if `obj.effective_to and obj.effective_to < timezone.localdate()`, redirect with an error message.

### [I12] Missing Ownership / Admin Enforcement on Quota Plan Submission and Edits
- **Location:** `apps/sales/views/TerritoryQuotaManagement/QuotaPlans.py:243-286`
- **Description:** `quota_plan_edit` and `quota_plan_submit` only check `@login_required` without verifying that `request.user` is either the plan owner or a tenant admin.
- **Fix:** Enforce ownership or tenant admin check in `quota_plan_edit` and `quota_plan_submit`: `if obj.owner_id and obj.owner_id != request.user.pk and not is_tenant_admin(request.user):`.

### [I13] Missing `@tenant_admin_required` on `territory_member_create` and `territory_member_edit`
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryMembers.py:115, 158`
- **Description:** While `territory_member_delete` enforces `@tenant_admin_required`, member create and edit only require `@login_required`, allowing non-admin users to alter territory rosters and split percentages.
- **Fix:** Add `@tenant_admin_required` to `territory_member_create` and `territory_member_edit`.

### [I14] Cross-Table Foreign Key Lookups in `Meta.ordering`
- **Location:** `apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py:134`, `TerritoryMembers.py:91`, `AccountTerritoryAssignments.py:100`
- **Description:** Ordering by foreign table columns (`territory__name`, `account__name`) forces automatic `INNER JOIN`s on all default queries.
- **Fix:** Prefer primary model fields in default `ordering` (e.g. `("-effective_from", "id")`) and order by related fields explicitly in views where needed.

---

## Minor

### [M1] Extraneous Pagination Partial on Detail Templates
- **Location:** `templates/sales/territoryquotamanagement/{territoryrule,accountterritoryassignment,territorymember,quotaplan}/detail.html`
- **Description:** All four detail templates include `{% include "partials/pagination.html" %}`, rendering redundant pagination markup on single-record views.
- **Fix:** Remove the include tag from the four detail templates.

### [M2] Potential `ObjectDoesNotExist` in `AccountTerritoryAssignment.__str__`
- **Location:** `apps/sales/models/TerritoryQuotaManagement/AccountTerritoryAssignments.py:192-193`
- **Description:** Evaluating `self.account` in `__str__` without guarding `self.account_id` raises `Party.DoesNotExist` on unpersisted or partially initialized instances.
- **Fix:** Use `getattr(self.account, "name", "—") if self.account_id else "—"`.

### [M3] Help Text Drift in `TerritoryRuleForm`
- **Location:** `apps/sales/forms/TerritoryQuotaManagement/TerritoryRules.py:94-96`
- **Description:** Form help text cites "at most 50 conditions and at most 4 KiB", whereas `validate_territory_conditions` strictly enforces `MAX_ROUTING_CONDITIONS = 20` and `MAX_ROUTING_JSON_BYTES = 16 * 1024`.
- **Fix:** Update help text to reflect 20 conditions and 16 KiB.

### [M4] Multiplier Division Guard in `derive_baseline` Does Not Guard Negative Values
- **Location:** `apps/sales/views/TerritoryQuotaManagement/QuotaPlans.py:102`
- **Description:** `derive_baseline` checks `if multiplier == 0:`. If extreme parameters are entered where attrition relief exceeds `100 + growth_target_pct`, `multiplier` becomes negative.
- **Fix:** Change `if multiplier == 0:` to `if multiplier <= 0:`.

### [M5] Parity in Navigation Extra Live Leaves for Account Territory Assignments
- **Location:** `apps/core/navigation.py:2425-2430`
- **Description:** `LIVE_LINKS["8.7"]` defines extra live leaves for "Territory Rules", "Territory Members", and "Quota Plans", but omits a direct noun extra leaf for "Account Territory Assignments".
- **Fix:** Add `"Account Territory Assignments": "sales:account_territory_assignment_list"` to `LIVE_LINKS["8.7"]` in `apps/core/navigation.py`.

### [M6] Multiple Serial `.count()` Round-trips for Header Statistics
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryRules.py:104-114`, `AccountTerritoryAssignments.py:112-120`
- **Description:** 4 separate `.filter(...).count()` round-trips can be combined into conditional `aggregate()`.
- **Fix:** Optimize to single aggregate query where appropriate.

### [M7] Missing `select_related("territory")` in `territory_performance`
- **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:677-697`
- **Description:** `plans_qs` does not `select_related("territory")`, resulting in N+1 queries when accessing `plan.territory`.
- **Fix:** Add `select_related("territory", "quota_ref", "forecast_period__reporting_currency")` to `plans_qs`.

### [M8] Missing Composite Indexes on Hot Assignment and Member Lookups
- **Location:** `apps/sales/models/TerritoryQuotaManagement/AccountTerritoryAssignments.py:107`, `TerritoryMembers.py:98`
- **Description:** Queries frequently filter on `(tenant, territory, effective_to)`.
- **Fix:** Ensure composite indexes cover common lookup combinations.

### [M9] Chained N+1 Queries Through Model `__str__` Methods
- **Location:** `AccountTerritoryAssignments.py:192-195`, `TerritoryMembers.py:120-123`
- **Description:** Calling `str(instance)` when `account`, `territory`, or `user` are un-prefetched incurs additional queries.
- **Fix:** Guard access or prefetch related FKs in list and board views.
