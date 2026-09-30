# Review Findings: Sales 8.7 Territory & Quota Management

Review of `02d8aa79...HEAD` across the 6-reviewer sequence.

---

## Pass 1: code-reviewer

### Critical
1. **Foreign Key Display Crash in `territory_performance` Board**
   - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:724`
   - **Description:** Line 724 executes `period.get_reporting_currency_display()`. `ForecastPeriod.reporting_currency` is a ForeignKey to `accounting.Currency`, not a field with `choices`. Invoking `get_FIELD_display()` on a foreign key triggers `AttributeError: 'ForecastPeriod' object has no attribute 'get_reporting_currency_display'`, crashing the territory performance board whenever deal currencies differ from reporting currency.
   - **Fix:** Change `period.get_reporting_currency_display()` to `(period.reporting_currency.code if period.reporting_currency else "—")` or `str(period.reporting_currency)`.

2. **Invalid Rule Condition Operator `"equals"` in `seed_sales.py`**
   - **Location:** `apps/sales/management/commands/seed_sales.py:1429, 1446`
   - **Description:** Seeded rules `rule_geo` and `rule_size` define conditions using `"operator": "equals"`. However, `ROUTING_OPERATORS` in `apps/sales/models/TerritoryQuotaManagement/TerritoryRules.py:44-54` only permits `"eq"`, `"ne"`, `"gt"`, `"gte"`, `"lt"`, `"lte"`, `"in"`, `"not_in"`, `"contains"`. This causes `_condition_matches` to fail to recognize `"equals"`, silently returning `False` for all evaluated accounts, and any clean/save triggers `ValidationError: Unsupported territory operator: equals`.
   - **Fix:** Change `"operator": "equals"` to `"operator": "eq"` at lines 1429 and 1446 in `seed_sales.py`.

3. **Broken Split Sum Validation in `TerritoryMember._check_split_sums`**
   - **Location:** `apps/sales/models/TerritoryQuotaManagement/TerritoryMembers.py:173-185`
   - **Description:**
     1. Line 173 checks `if not siblings.filter(assignment_type="shared").exists(): return`. When creating the very first shared member on a territory, `self` is not yet in `siblings`, causing the check to exit early without validating direct splits against 100%.
     2. Line 180 calculates `total = sum(...) + (self.coverage_split_pct or Decimal("0"))`. It adds `self.coverage_split_pct` even when `self.assignment_type != "direct"`. If a territory already has 100% direct split coverage and an admin attempts to add an `overlay` specialist or a `shared` rep, `total` becomes 100 + split (e.g. 120%), raising a false `ValidationError` and blocking valid overlay/shared assignments.
   - **Fix:** Gate validation on `if self.assignment_type != "shared" and not siblings.filter(assignment_type="shared").exists(): return`. Only add `self.coverage_split_pct` into `total` when `self.assignment_type == "direct"`.

4. **Truthy Evaluation of `None` in `TerritoryMember._paired_user_is_ae`**
   - **Location:** `apps/sales/models/TerritoryQuotaManagement/TerritoryMembers.py:131, 146-155`
   - **Description:**
     1. `_paired_user_is_ae()` returns `None` when pairing cannot be judged. Line 131 uses `if self.paired_user_id and not self._paired_user_is_ae():`. In Python, `not None` evaluates to `True`, triggering a spurious `"A pairing must point at a member whose role is Account Executive."` validation error when the paired user cannot be found or is cross-tenant.
     2. Line 150 uses `.first()`, which returns an arbitrary row if a user holds multiple memberships.
   - **Fix:** Change line 131 to `if self.paired_user_id and self._paired_user_is_ae() is False:`. Query `.filter(tenant_id=self.tenant_id, territory_id=self.territory_id, user_id=self.paired_user_id, member_role="ae").exists()`.

### Important
5. **Unfiltered Foreign Key Dropdowns in Model Forms (Tenant Isolation Breach)**
   - **Location:** `apps/sales/forms/TerritoryQuotaManagement/TerritoryMembers.py:84-93`, `apps/sales/forms/TerritoryQuotaManagement/QuotaPlans.py:119-128`
   - **Description:**
     - `TerritoryMemberForm.__init__` leaves `self.fields["territory"].queryset` unconstrained, displaying territories across all tenants.
     - `QuotaPlanForm.__init__` fails to filter `self.fields["territory"].queryset` and `self.fields["owner"].queryset`, exposing all territories and all platform users across workspaces.
   - **Fix:** Scope `self.fields["territory"].queryset` to active same-tenant territories in `TerritoryMemberForm` and `QuotaPlanForm`, and scope `self.fields["owner"].queryset` to active same-tenant users in `QuotaPlanForm`.

6. **Invariant Violation in `territory_rule_run` with Subtree Primary Rules**
   - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryRules.py:271-280`
   - **Description:** When a rule has `assignment_scope="subtree"` and `alignment_type="primary"`, `evaluate_territory_rules` generates diff entries for the target territory and all descendant territories. In `territory_rule_run`, `AccountTerritoryAssignment.objects.create(alignment_type="primary", ...)` executes for each territory. Because `.create()` bypasses `clean()`, multiple active primary assignments are created for the same account, violating the invariant that an account can have at most one active primary territory.
   - **Fix:** In `TerritoryRule.clean()`, forbid `alignment_type == "primary"` when `assignment_scope == "subtree"`, or restrict automated subtree assignments in `territory_rule_run` to secondary/overlay alignments.

7. **Potential Unhandled `DoesNotExist` in `QuotaPlan.clean()`**
   - **Location:** `apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py:178, 184`
   - **Description:** `self.quota_ref` and `self.forecast_period` are dereferenced directly in `clean()`. If `quota_ref_id` points to a non-existent or foreign-tenant record, accessing `self.quota_ref` raises `crm.SalesQuota.DoesNotExist` instead of returning validation errors.
   - **Fix:** Check `if "quota_ref" in errors or "forecast_period" in errors:` and skip direct attribute access when foreign keys failed tenant validation.

8. **Overwriting Stamped `assigned_by` on Assignment Edit**
   - **Location:** `apps/sales/views/TerritoryQuotaManagement/AccountTerritoryAssignments.py:213`
   - **Description:** `locked.assigned_by = request.user` is executed during `account_territory_assignment_edit`. Per contract §12 and model specification, `assigned_by` is immutable origin evidence stamped at creation to record who assigned the account. Overwriting it on edit destroys historical attribution.
   - **Fix:** Remove `locked.assigned_by = request.user` from `account_territory_assignment_edit`.

9. **Missing Frozen State Check in `QuotaPlan.clean()`**
   - **Location:** `apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py:167-204`
   - **Description:** Contract §6.5 rule 7 mandates that plans in `FROZEN_STATES` cannot be edited. While the edit view guards this, `QuotaPlan.clean()` does not enforce it at the model level, leaving models vulnerable to modification via shell or scripts.
   - **Fix:** In `QuotaPlan.clean()`, check if `self.pk` and current status in DB is in `FROZEN_STATES`, and raise `ValidationError`.

### Minor
10. **Potential `ObjectDoesNotExist` in `AccountTerritoryAssignment.__str__`**
    - **Location:** `apps/sales/models/TerritoryQuotaManagement/AccountTerritoryAssignments.py:192-193`
    - **Description:** Evaluating `self.account` in `__str__` without guarding `self.account_id` raises `Party.DoesNotExist` on unpersisted or partially initialized instances.
    - **Fix:** Use `getattr(self.account, "name", "—") if self.account_id else "—"`.

11. **Extraneous Pagination Partial on Detail Templates**
    - **Location:** `templates/sales/territoryquotamanagement/territoryrule/detail.html:61`, `templates/sales/territoryquotamanagement/accountterritoryassignment/detail.html:61`, `templates/sales/territoryquotamanagement/territorymember/detail.html:57`, `templates/sales/territoryquotamanagement/quotaplan/detail.html:77`
    - **Description:** All four detail templates include `{% include "partials/pagination.html" %}`, rendering redundant pagination markup on single-record views.
    - **Fix:** Remove the include tag from the four detail templates.

12. **Help Text Drift in `TerritoryRuleForm`**
    - **Location:** `apps/sales/forms/TerritoryQuotaManagement/TerritoryRules.py:94-96`
    - **Description:** Form help text cites "at most 50 conditions and at most 4 KiB", whereas `validate_territory_conditions` strictly enforces `MAX_ROUTING_CONDITIONS = 20` and `MAX_ROUTING_JSON_BYTES = 16 * 1024`.
    - **Fix:** Update help text to reflect 20 conditions and 16 KiB.

---

## Pass 2: explorer

### Critical
(Confirmed Findings 1 & 2 from Pass 1)

### Important
13. **Coverage Gap Board Falsely Flags All Non-SDR Members as Orphaned SDR Pairings**
    - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:562-566`
    - **Description:** `orphaned_pair_rows` query in `territory_coverage_gap` is missing `.filter(member_role="sdr")`. Without this filter, every active Hunter, Farmer, AE, Overlay Specialist, and Sales Engineer with `paired_user=None` is displayed in the "SDR pairings with no active account executive" table and tallied in the board caveats.
    - **Fix:** Add `.filter(member_role="sdr")` to `orphaned_pair_rows` in `TerritoryBoards.py:563`.

### Minor
14. **Multiplier Division Guard in `derive_baseline` Does Not Guard Negative Values**
    - **Location:** `apps/sales/views/TerritoryQuotaManagement/QuotaPlans.py:102`
    - **Description:** `derive_baseline` checks `if multiplier == 0:`. If extreme parameters are entered where attrition relief exceeds `100 + growth_target_pct`, `multiplier` becomes negative, resulting in a negative derived baseline figure rather than a cautionary message.
    - **Fix:** Change `if multiplier == 0:` to `if multiplier <= 0:`.

15. **Parity in Navigation Extra Live Leaves for Account Territory Assignments**
    - **Location:** `apps/core/navigation.py:2425-2430`
    - **Description:** `LIVE_LINKS["8.7"]` defines extra live leaves for "Territory Rules", "Territory Members", and "Quota Plans", but omits a direct noun extra leaf for "Account Territory Assignments".
    - **Fix:** Add `"Account Territory Assignments": "sales:account_territory_assignment_list"` to `LIVE_LINKS["8.7"]` in `apps/core/navigation.py`.

---

## Pass 3: frontend-reviewer

### Critical
16. **Broken Condition Value Rendering in `territoryrule/detail.html` via `|join:", "` on Scalars**
    - **Location:** `templates/sales/territoryquotamanagement/territoryrule/detail.html:91`
    - **Description:** Line 91 applies `|join:", "` unconditionally to `condition.value`. In `TerritoryRule.conditions`, `condition["value"]` is only a list for `in` and `not_in` operators; for all other operators it is a scalar string, number, or boolean. Applying `|join:", "` iterates strings character-by-character (e.g. `"Enterprise"` renders as `"E, n, t, e, r, p, r, i, s, e"`).
    - **Fix:** Check `{% elif condition.operator == "in" or condition.operator == "not_in" %}{{ condition.value|join:", " }}{% else %}{{ condition.value }}{% endif %}`.

### Important
17. **Unapproved `stat-icon red` Class Used Across 8 Templates**
    - **Location:**
      1. `templates/sales/territoryquotamanagement/accountterritoryassignment/detail.html:32`
      2. `templates/sales/territoryquotamanagement/accountterritoryassignment/list.html:33`
      3. `templates/sales/territoryquotamanagement/boards/coverage_gap.html:52`
      4. `templates/sales/territoryquotamanagement/boards/coverage_gap.html:55`
      5. `templates/sales/territoryquotamanagement/boards/rebalance_preview.html:52`
      6. `templates/sales/territoryquotamanagement/boards/white_space.html:53`
      7. `templates/sales/territoryquotamanagement/quotaplan/detail.html:38`
      8. `templates/sales/territoryquotamanagement/territorymember/list.html:34`
    - **Description:** Under the NavERP design system (L33), stat icons are strictly limited to `blue`, `green`, `orange`, `purple`, and `slate`. `red` is unstyled.
    - **Fix:** Replace `red` with `orange` (or `slate`) across all 8 stat-card declarations.

### Minor
(Confirmed Finding 11 on Extraneous `{% include "partials/pagination.html" %}` on 4 detail templates)

---

## Pass 4: performance-reviewer

### Critical
18. **In-Loop `select_for_update` Queries in `territory_rule_run`**
    - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryRules.py:246-281`
    - **Description:** For each diff entry, `territory_rule_run` issues a separate `select_for_update` on `AccountTerritoryAssignment` inside the loop. Under larger dry runs, this creates serial row locks and high latency.
    - **Fix:** Bulk fetch/lock candidate assignments outside the loop or batch primary assignment deactivations.

19. **Unbounded Assignment Evaluation and SQL `IN (...)` Parameter List in `territory_performance`**
    - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:663-712`
    - **Description:** `territory_performance` extracts all assignment IDs into memory and issues `IN (...)` queries over deals and orders. On large tenants with thousands of accounts, this can exceed SQL parameter limits and cause slow response times.
    - **Fix:** Use subquery `party_id__in=AccountTerritoryAssignment.objects.filter(...).values('account_id')` directly in the query.

20. **In-Memory Post-Slice Filtering in `territory_white_space` and `rebalance_preview`**
    - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:860-932`
    - **Description:** `accounts = list(accounts_qs[:MAX_BOARD_ACCOUNTS])` slices the accounts first, and then in-memory loops apply coverage/tier/industry filtering. If the first `MAX_BOARD_ACCOUNTS` accounts do not match the filter, the board displays zero rows even when matching accounts exist beyond the slice.
    - **Fix:** Apply tier, industry, and classification filters directly on the database `accounts_qs` before applying `[:MAX_BOARD_ACCOUNTS]`.

### Important
21. **Redundant Duplicate Queries on `AccountProfile` and `AccountClassification` Across Boards**
    - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:138-147, 298-307, 423-432, 514-521`
    - **Description:** Helper functions `_build_account_profile_map` and `_build_account_classification_map` are invoked repeatedly across helper routines, creating duplicated queries for the same account IDs.
    - **Fix:** Pass cached/precomputed profile and classification maps through board helper functions rather than re-querying.

22. **Unbounded Evaluation and In-Memory Substring Search in `territory_coverage_gap`**
    - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:555-561`
    - **Description:** Orphan account rows are collected into a Python list and filtered via Python `q_filter in acc["name"].lower()` rather than DB filtering with `.filter(name__icontains=q_filter)`.
    - **Fix:** Filter candidate parties by `q_filter` at the database level when possible before building orphan structures.

23. **Missing `select_related("territory")` and Display Crash in `territory_performance`**
    - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py:677-697, 724`
    - **Description:** `plans_qs` does not `select_related("territory")`, resulting in N+1 queries when accessing `plan.territory`. Also confirms Finding 1 regarding `period.get_reporting_currency_display()`.
    - **Fix:** Add `select_related("territory", "quota_ref", "forecast_period__reporting_currency")` to `plans_qs`.

24. **Cross-Table Foreign Key Lookups in `Meta.ordering`**
    - **Location:** `apps/sales/models/TerritoryQuotaManagement/QuotaPlans.py:134`, `TerritoryMembers.py:91`, `AccountTerritoryAssignments.py:100`
    - **Description:** Ordering by foreign table columns (`territory__name`, `account__name`) forces automatic `INNER JOIN`s on all default queries.
    - **Fix:** Prefer primary model fields in default `ordering` (e.g. `("-effective_from", "id")`) and order by related fields explicitly in views where needed.

25. **Missing Composite Index on Hot Assignment and Member Lookups**
    - **Location:** `apps/sales/models/TerritoryQuotaManagement/AccountTerritoryAssignments.py:107`, `TerritoryMembers.py:98`
    - **Description:** Queries frequently filter on `(tenant, territory, effective_to)`.
    - **Fix:** Ensure composite indexes cover common lookup combinations.

### Minor
26. **Multiple Serial `.count()` Round-trips for Header Statistics**
    - **Location:** `apps/sales/views/TerritoryQuotaManagement/TerritoryRules.py:104-114`, `AccountTerritoryAssignments.py:112-120`
    - **Description:** 4 separate `.filter(...).count()` round-trips can be combined into conditional `aggregate()`.
    - **Fix:** Optimize to single aggregate query where appropriate.

27. **Chained N+1 Queries Through Model `__str__` Methods**
    - **Location:** `AccountTerritoryAssignments.py:192-195`, `TerritoryMembers.py:120-123`
    - **Description:** Calling `str(instance)` when `account`, `territory`, or `user` are un-prefetched incurs additional queries.
    - **Fix:** Guard access or prefetch related FKs in list and board views.



