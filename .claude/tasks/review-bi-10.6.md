# Review Findings — Sub-module 10.6: Master Data Management (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.6 Master Data Management
- **Module:** 10 Business Intelligence
- **Target app:** `apps/bi`
- **Review date:** 2026-11-04
- **Base SHA:** `bdddf111e168a926f9d666c5784c89ceedfdebdd`
- **Status:** Complete (All 6 Review Passes Finished: code-reviewer, explorer, frontend-reviewer, performance-reviewer, qa-smoke-tester, security-reviewer)

---

## Prioritized Findings (Deduplicated)

### Critical Findings

- [x] **[C1] Universal `write_audit_log` parameter mismatch crashes all 15 POST mutations across all 4 entities with HTTP 500** — fixed in `80f6ccd7`, `4039c1b1`, `2ec6c25b`, `0e9e6c91`
  - **Found by:** code-reviewer, qa-smoke-tester, security-reviewer
  - **Locations:**
    - `apps/bi/views/MasterData/MdmGoldenRecords.py:121, 148, 174, 213, 253, 273` (`create`, `edit`, `delete`, `merge`, `unmerge`, `approve`)
    - `apps/bi/views/MasterData/MdmHierarchyNodes.py:90, 117, 143` (`create`, `edit`, `delete`)
    - `apps/bi/views/MasterData/MdmReferenceCodes.py:85, 112, 138` (`create`, `edit`, `delete`)
    - `apps/bi/views/MasterData/MdmSurvivorshipRules.py:88, 115, 141` (`create`, `edit`, `delete`)
  - **Description:** `write_audit_log` utility signature in `apps/core/utils.py` is `(user, obj, action, changes=None, tenant=None)` but was called with incompatible keyword arguments `request=request, action=..., instance=..., changes=...`. This causes an unhandled `TypeError: write_audit_log() got an unexpected keyword argument 'request'` on every write operation, crashing all POST endpoints with HTTP 500 and preventing compliance audit log generation.
  - **Fix:** Update all 15 call sites across the 4 view files to `write_audit_log(request.user, <instance>, "<action>", changes=..., tenant=request.tenant)`. On delete views, invoke before `instance.delete()`.

---

### Important Findings

- [x] **[I1] `mdm_golden_record_approve` lacks status guard for merged duplicate records** — fixed in `cd4003f3`
  - **Found by:** explorer, security-reviewer
  - **Location:** `apps/bi/views/MasterData/MdmGoldenRecords.py:266`
  - **Description:** Directly approving an absorbed record (`golden_record.status = "approved"`) without clearing merge metadata revives it as an active certified master record, creating duplicate conflicting golden records.
  - **Fix:** Add status check at top of `mdm_golden_record_approve`:
    ```python
    if golden_record.status == "merged":
        messages.error(request, "Merged records cannot be certified directly. Unmerge the record before approval.")
        return redirect("bi:mdm_golden_record_detail", pk=golden_record.pk)
    ```

- [x] **[I2] `mdm_golden_record_merge` allows merging into already merged records and lacks candidate re-check** — fixed in `83806dc8`
  - **Found by:** code-reviewer, explorer, security-reviewer
  - **Location:** `apps/bi/views/MasterData/MdmGoldenRecords.py:187-227`
  - **Description:** No validation ensures `primary_record.status != "merged"`. An attacker or steward could merge candidate records into an already absorbed record, creating circular or nested merge chains.
  - **Fix:** Add validation in `mdm_golden_record_merge`:
    ```python
    if primary_record.status == "merged":
        messages.error(request, "Cannot merge candidate records into an already absorbed master record.")
        return redirect("bi:mdm_golden_record_detail", pk=primary_record.pk)
    if secondary_record.status == "merged":
        messages.error(request, "Selected candidate record has already been absorbed.")
        return redirect("bi:mdm_golden_record_detail", pk=primary_record.pk)
    ```

- [x] **[I3] Mass assignment: `status="merged"` exposed in manual Golden Record create/edit forms** — fixed in `fe31b2ce`
  - **Found by:** security-reviewer
  - **Location:** `apps/bi/forms/MasterData/MdmGoldenRecordForms.py:15-37`
  - **Description:** Exposes `merged` in `status` choices on `MdmGoldenRecordForm`, allowing users to manually set `status="merged"` without a surviving record, creating orphaned merged records that cannot be unmerged.
  - **Fix:** In `MdmGoldenRecordForm.__init__`, filter `status` choices to exclude `"merged"`:
    ```python
    self.fields["status"].choices = [c for c in MdmGoldenRecord.STATUS_CHOICES if c[0] != "merged"]
    ```

- [x] **[I4] Deletion of surviving master record leaves absorbed records in orphaned "merged" state** — fixed in `07babd36`
  - **Found by:** security-reviewer
  - **Location:** `apps/bi/views/MasterData/MdmGoldenRecords.py:168-183`
  - **Description:** Because `merged_into_record` is `SET_NULL`, deleting an active golden record holding absorbed duplicates clears their `merged_into_record_id` while leaving `status="merged"`, stranding them permanently where they can never be unmerged.
  - **Fix:** In `mdm_golden_record_delete`, block deletion if absorbed records exist:
    ```python
    if golden_record.absorbed_records.exists():
        messages.error(request, f"Cannot delete {golden_record.number} because it has absorbed duplicate records. Unmerge them first.")
        return redirect("bi:mdm_golden_record_detail", pk=golden_record.pk)
    ```

- [x] **[I5] `mdm_golden_record_unmerge` source record count decrement asymmetry and unconditional `'approved'` promotion** — fixed in `4fde6217`
  - **Found by:** code-reviewer, explorer, security-reviewer
  - **Location:** `apps/bi/views/MasterData/MdmGoldenRecords.py:241-251`
  - **Description:** Unmerging decrements by 1 instead of restoring absorbed count, and unconditionally sets status to `'approved'` even if the record was previously in `'draft'` or `'pending_review'`.
  - **Fix:** Deduct `absorbed_record.source_record_count` (`surviving_record.source_record_count = max(1, surviving_record.source_record_count - absorbed_record.source_record_count)`) and set `absorbed_record.status = "pending_review"` for steward verification. Also defensively assert `surviving_record.tenant_id == request.tenant.id`.

- [x] **[I6] `mdm_golden_record_merge` does not consolidate `source_crosswalks_json`** — fixed in `790d4cf3`
  - **Found by:** code-reviewer, security-reviewer
  - **Location:** `apps/bi/views/MasterData/MdmGoldenRecords.py:195-212`
  - **Description:** When merging duplicate records, `secondary_record.source_crosswalks_json` is not appended to `primary_record.source_crosswalks_json`. Feeder system identifier crosswalks are lost from the active golden record.
  - **Fix:** Append secondary crosswalks to primary crosswalk list inside `transaction.atomic()`.

- [x] **[I7] `MdmHierarchyNodeForm` does not validate matching `hierarchy_type` between parent and child** — fixed in `bc79797e`
  - **Found by:** code-reviewer, explorer
  - **Location:** `apps/bi/forms/MasterData/MdmHierarchyNodeForms.py:60-74`
  - **Description:** Allows cross-hierarchy parent assignments (e.g. product category inside legal entity tree).
  - **Fix:** Validate `parent.hierarchy_type == cleaned.get("hierarchy_type")` in form `clean()`.

- [x] **[I8] Materialized `path` and `level` are not cascaded to child descendants on parent update** — fixed in `b23aa252`
  - **Found by:** explorer
  - **Location:** `apps/bi/models/MasterData/MdmHierarchyNodes.py:100`
  - **Description:** When a node's parent changes, child descendants retain stale path/level.
  - **Fix:** Cascade descendant paths and levels recursively when `parent_id` changes.

- [x] **[I9] `MdmSurvivorshipRuleForm` lacks threshold logic validation (`auto_merge_threshold_pct >= match_threshold_pct`)** — fixed in `76293e1f`
  - **Found by:** code-reviewer, security-reviewer
  - **Location:** `apps/bi/forms/MasterData/MdmSurvivorshipRuleForms.py:84-88`
  - **Description:** Auto-merge threshold can be configured lower than manual review threshold.
  - **Fix:** Add validation in form `clean()` that `auto_merge_threshold_pct >= match_threshold_pct`.

- [x] **[I10] Subpackage `__init__.py` files in `MasterData/` missing re-exports** — fixed in `0a8e7a9b`, `7f68265f`, `8289d270`
  - **Found by:** code-reviewer, explorer
  - **Locations:** `apps/bi/models/MasterData/__init__.py:1`, `apps/bi/forms/MasterData/__init__.py:1`, `apps/bi/views/MasterData/__init__.py:1`
  - **Description:** Placeholder comments only, no imports or `__all__`.
  - **Fix:** Re-export all models, forms, and views with explicit `__all__` lists in each `MasterData/__init__.py`.

- [x] **[I11] Missing standard POST Delete action on Golden Record Detail view** — fixed in `19c76aa6`
  - **Found by:** frontend-reviewer, explorer, code-reviewer
  - **Location:** `templates/bi/master_data/golden_record/detail.html:41-60`
  - **Description:** Detail templates in NavERP must provide Edit, Back to List, and a POST Delete action with CSRF and confirm prompt.
  - **Fix:** Add standard POST delete form/button in `golden_record/detail.html`.

- [x] **[I12] Missing alert banner linking to surviving master record on absorbed duplicate records** — fixed in `7705377f`
  - **Found by:** frontend-reviewer
  - **Location:** `templates/bi/master_data/golden_record/detail.html:17-40`
  - **Description:** When inspecting an absorbed record (`status == 'merged'`), no link or alert banner guides the user to the surviving master record (`golden_record.merged_into_record`).
  - **Fix:** Add alert banner linking to `golden_record.merged_into_record` when `status == 'merged'`.

- [x] **[I13] Unconsolidated Stat Card Queries Across Overview and List Views** — fixed in `0bef50e7`, `24223ebf`, `f19bd214`, `d1d69b44`, `37182205`
  - **Found by:** performance-reviewer
  - **Locations:** `apps/bi/views/MasterData/MdmOverviewViews.py:19-25`, `MdmGoldenRecords.py:51-56`, `MdmSurvivorshipRules.py:43-46`, `MdmHierarchyNodes.py:39-42`, `MdmReferenceCodes.py:40-43`
  - **Description:** Multiple separate `COUNT(*)` queries on every list/overview load.
  - **Fix:** Consolidate into single conditional `.aggregate(Count('id', filter=Q(...)))` calls.

- [x] **[I14] Heavy JSON & Full-Row Over-fetching in ModelChoiceField Dropdowns** — fixed in `435af804`, `766236ba`, `bdc61ceb`
  - **Found by:** performance-reviewer
  - **Locations:** `apps/bi/forms/MasterData/MdmGoldenRecordForms.py:98-103`, `apps/bi/forms/MasterData/MdmHierarchyNodeForms.py:55`, `apps/bi/forms/MasterData/MdmReferenceCodeForms.py:64`
  - **Description:** Form dropdown querysets load all columns and large JSON fields into Python memory.
  - **Fix:** Add `.only(...)` to project only the fields needed by select widgets.

- [x] **[I15] Missing Composite Database Indexes for Hot Filtered/Sorted Columns** — fixed in `f63a88d8`, `11179876`, `562987d5`, `ae75d8c2`
  - **Found by:** performance-reviewer
  - **Locations:** `apps/bi/models/MasterData/MdmSurvivorshipRules.py`, `MdmHierarchyNodes.py`, `MdmGoldenRecords.py`
  - **Description:** Missing composite indexes on `(tenant, match_algorithm)` in MdmSurvivorshipRule, `(tenant, hierarchy_type, level)` in MdmHierarchyNode, and `(tenant, -created_at)` in MdmGoldenRecord.
  - **Fix:** Add indexes in `Meta.indexes` and generate migration.

---

### Minor Findings

- [x] **[M1] Pinned contract variable `hierarchy_nodes` omitted from `golden_record/detail.html`** — fixed in `a1bb8dfd`
  - **Location:** `templates/bi/master_data/golden_record/detail.html:275`
  - **Fix:** Render linked hierarchy node cards with links to node detail.

- [x] **[M2] Redundant duplicate queries in detail templates via `.exists` and `.count`** — fixed in `83dcab0d`, `9b8b6781`, `482c01c6`
  - **Locations:** `templates/bi/master_data/reference_code/detail.html:114, 129, 133`, `golden_record/detail.html:229, 242`, `hierarchy_node/detail.html:103, 118`
  - **Fix:** Pre-evaluate into lists in views or use `{% if relation %}` and `{{ relation|length }}` in templates.

- [x] **[M3] Missing `aria-label` and `title` on pagination previous and next links** — fixed in `39e39004`, `88acd4e9`, `3944ad3d`, `6a3de151`
  - **Locations:** `list.html` across all 4 entities
  - **Fix:** Add `aria-label="Previous page"` and `aria-label="Next page"`.

- [x] **[M4] Missing `aria-label` attributes on table action and filter icon buttons** — fixed in `c62b7756`, `08e5a4ab`, `4b491af5`, `0455e1ea`
  - **Locations:** `list.html` and `detail.html` across all 4 entities
  - **Fix:** Add `aria-label` attributes matching `title`.

- [x] **[M5] Confirmation prompt on submit button instead of form `onsubmit` in merge workbench** — fixed in `dd719287`
  - **Location:** `templates/bi/master_data/golden_record/detail.html:323, 336`
  - **Fix:** Move `onsubmit="return confirm(...)"` to the `<form>` element.

- [x] **[M6] Percentage metric fields lack min/max validators** — fixed in `39a8d3c2`, `5bfa83d1`, `aaae78be`
  - **Locations:** `MdmGoldenRecord.confidence_score`, `MdmSurvivorshipRule.match_threshold_pct`, `auto_merge_threshold_pct`
  - **Fix:** Add `MinValueValidator(Decimal("0.00"))` and `MaxValueValidator(Decimal("100.00"))`.

- [x] **[M7] Over-fetching Foreign Keys via Unused `select_related` in Golden Record List & Overview** — fixed in `6d364d72`, `069fd49b`, `430d600a`
  - **Locations:** `MdmGoldenRecords.py:24-27`, `MdmSurvivorshipRules.py:19`, `MdmOverviewViews.py:38-41`
  - **Fix:** Prune unused joins to only what the templates render.

- [x] **[M8] Non-standard parameter signature in `MdmGoldenRecordMergeForm`** — fixed in `5bd2afe9`, `d7a70de3`
  - **Location:** `apps/bi/forms/MasterData/MdmGoldenRecordForms.py:96`
  - **Fix:** Use standard `def __init__(self, *args, tenant=None, primary_record=None, **kwargs):`.

- [x] **[M9] `reviewed_by` steward omitted from governance panel** — fixed in `edb97473`
  - **Location:** `templates/bi/master_data/golden_record/detail.html:103`
  - **Fix:** Display `Certified by {{ golden_record.reviewed_by.get_full_name|default:golden_record.reviewed_by.username }}` when present.

- [x] **[M10] Responsive grid empty-state colspan in MDM overview domain distribution** — fixed in `12170d7f`
  - **Location:** `templates/bi/master_data/mdm_overview.html:98-101`
  - **Fix:** Change `col-span-3` to `col-span-full`.

- [x] **[M11] `total_rules` and `total_reference_codes` context keys not rendered in `mdm_overview.html`** — fixed in `8ca0107d`
  - **Location:** `templates/bi/master_data/mdm_overview.html:41`
  - **Fix:** Display total count badges on the Survivorship Policies and Reference Code Sets cards.

---

## Pass-by-Pass Raw Findings History

### Pass 1: Code Reviewer (`code-reviewer`) Findings
- **[CR-C1]** `write_audit_log` keyword argument signature mismatch crashes all write views
- **[CR-I1]** `mdm_golden_record_merge` allows merging into already merged records
- **[CR-I2]** `mdm_golden_record_unmerge` source record count decrement asymmetry
- **[CR-I3]** `mdm_golden_record_merge` does not consolidate `source_crosswalks_json`
- **[CR-I4]** `MdmHierarchyNodeForm` does not validate matching `hierarchy_type`
- **[CR-I5]** `MdmSurvivorshipRuleForm` lacks threshold logic validation
- **[CR-I6]** Package `__init__.py` files in `MasterData/` missing re-exports
- **[CR-M1]** `hierarchy_nodes` context variable passed to `mdm_golden_record_detail` is unrendered
- **[CR-M2]** `mdm_golden_record_unmerge` unconditionally sets status to `'approved'`
- **[CR-M3]** Percentage fields lack min/max validators
- **[CR-M4]** `MdmHierarchyNode.save()` fallback when `parent.path` is empty
- **[CR-M5]** Missing Delete button on `golden_record/detail.html`
- **[CR-M6]** Redundant `COUNT(*)` query in `detail.html`

### Pass 2: Explorer (`explorer`) Findings
- **[EXP-I1]** Subpackage `__init__.py` files do not export package symbols
- **[EXP-I2]** `mdm_golden_record_approve` lacks status guard for merged duplicate records
- **[EXP-I3]** `mdm_golden_record_merge` lacks status validation for primary and secondary records
- **[EXP-I4]** Pinned contract variable `hierarchy_nodes` is omitted from `golden_record/detail.html`
- **[EXP-I5]** Materialized `path` and `level` are not cascaded to child descendants on parent update
- **[EXP-I6]** `MdmHierarchyNodeForm` does not validate tree homogeneity
- **[EXP-M1]** `mdm_golden_record_unmerge` decrements `source_record_count` by 1 instead of absorbed record's count
- **[EXP-M2]** `total_rules` and `total_reference_codes` context keys not rendered in `mdm_overview.html`
- **[EXP-M3]** Detail page lacks a Delete Record action
- **[EXP-M4]** `reviewed_by` steward is omitted from the governance panel
- **[EXP-M5]** Non-standard parameter signature in `MdmGoldenRecordMergeForm`

### Pass 3: Frontend Reviewer (`frontend-reviewer`) Findings
- **[FE-I1]** Missing standard POST Delete action on Golden Record Detail view
- **[FE-I2]** No visual banner or surviving master link on absorbed duplicate records
- **[FE-M1]** Missing `aria-label` and `title` on pagination previous and next links
- **[FE-M2]** Missing `aria-label` attributes on table action and filter icon buttons
- **[FE-M3]** Confirmation prompt on submit button instead of form `onsubmit` in merge workbench
- **[FE-M4]** Unrendered `hierarchy_nodes` context variable in Golden Record Detail view
- **[FE-M5]** Responsive grid empty-state colspan in MDM overview domain distribution

### Pass 4: Performance Reviewer (`performance-reviewer`) Findings
- **[PERF-I1]** Unconsolidated Stat Card Queries Across Overview and List Views
- **[PERF-I2]** Redundant Duplicate Queries in Detail Templates via `.exists` and `.count`
- **[PERF-I3]** Heavy JSON & Full-Row Over-fetching in ModelChoiceField Dropdowns
- **[PERF-I4]** Missing Composite Database Indexes for Hot Filtered/Sorted Columns
- **[PERF-M1]** Over-fetching Foreign Keys via Unused `select_related` in Golden Record List
- **[PERF-M2]** Over-fetching Foreign Key via Unused `select_related("steward")` in Survivorship Rule List & Overview
- **[PERF-M3]** Unused QuerySet in Context in Golden Record Detail View

### Pass 5: QA Smoke Tester (`qa-smoke-tester`) Findings
- **[QA-C1]** `write_audit_log` parameter mismatch crashes all POST mutation views with HTTP 500 (15 call sites)

### Pass 6: Security Reviewer (`security-reviewer`) Findings
- **[SEC-C1]** `write_audit_log` Parameter Mismatch Breaks Audit Trail Integrity & Causes DoS on All Writes
- **[SEC-I1]** Master Data State Machine Bypass: Direct Approval of Absorbed/Merged Records via POST
- **[SEC-I2]** Merge Lifecycle Bypass: Merging into Already Absorbed Records Allows Cyclic Consolidation
- **[SEC-I3]** Mass Assignment / Integrity Violation: `status="merged"` Exposed in Manual Create/Edit Forms
- **[SEC-I4]** Deletion of Surviving Master Record Leaves Absorbed Records in an Orphaned "Merged" State
- **[SEC-I5]** Unmerge Privilege / Status Escalation: Unmerging Unconditionally Certifies Records as `'approved'`
- **[SEC-I6]** Unvalidated Survivorship Threshold Logic Permits Auto-Merge Below Review Threshold
- **[SEC-M1]** Missing Defensive Tenant Validation in `mdm_golden_record_unmerge` for `surviving_record`
- **[SEC-M2]** Missing Min/Max Validators on Percentage Metric Fields
- **[SEC-M3]** Incomplete Crosswalk Merging During Golden Record Consolidation
