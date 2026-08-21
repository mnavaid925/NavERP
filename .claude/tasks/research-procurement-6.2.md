# Research — Module 6 Procurement, Sub-module 6.2 Requisition Management

Date: 2026-08-22 · Research-only phase. No code modified. Target contract: NavERP.md §6.2 bullets
(1) Requisition Creation, (2) Requisition Tracking, (3) Duplicate Requisition Check,
(4) Requisition Templates, (5) Requisition Cancellation/Amendment.

---

## 1. Product Survey (intake-to-order requisition management)

### SAP Ariba (Buying / Buying & Invoicing)
- **Creation:** catalog + non-catalog items compose a requisition; unique ID `PR2394`-style; team buying lets delegates act as the requester (edit/cancel/submit/withdraw).
- **Amendment semantics (richest model found):** amendments retain the parent ID with suffix `-A<n>` (`PR123-A1`, `PR123-A2`); amendment statuses `Composing / Submitted / Approved / Merged`. Approved amendments trigger new versions `PR123-Vx` and `PO456-Vx`; header fields merge last-wins, ONE open amendment per LINE at a time (locking); reason required; amendment-specific approval flow possible.
- **Cancel:** lifecycle includes `Canceling` → `Canceled`; admin-group ("Purchasing Approvable Administrator") can **Deactivate** stuck `Approved`/`Ordering` requisitions; deactivation makes the PREVIOUS version active again (versioned undo). Cannot revert Mark-as-Canceled.
- **Withdraw:** returns requisition to `Composing`; an APPROVED requisition can be withdrawn only while a "Delay Purchase Until" date still gates it.
- **Duplicate detection:** none native at requisition level (AI duplicate detection targets invoices/suppliers).
- URLs: https://help.sap.com/docs/buying-invoicing/approvables-reference-guide/purchase-requisition-or-requisition-pr · https://learning.sap.com/courses/managing-purchase-orders-in-sap-ariba-buying-and-invoicing/create-and-manage-purchase-order-amendments · https://support.ariba.com/item/view/KB1315094 · https://canadabuys.canada.ca/en/support/amending-or-cancelling-purchase-requisition-and-purchase-orders-sap-ariba · https://help.sap.com/docs/buying-invoicing/purchasing-guide-for-procurement-professionals/how-to-withdraw-and-edit-requisition · https://support.ariba.com/item/view/195888

### Oracle Fusion Procurement Cloud
- **Withdraw:** REST action `withdraw` on requisition/header/line — legal while approval is IN PROCESS, or after completion ONLY IF no line is tied to a PO / transfer order / negotiation / buyer modification. Withdraw moves document back to `Incomplete` for edit + resubmit.
- **Change order:** post-approval modifications go through a REQUESTER CHANGE ORDER flow (new version routed for re-approval) rather than editing the approved doc; UCSD/UChicago guides confirm cancel applies to incomplete/pending/rejected change orders.
- **Timing guard:** if approval hasn't STARTED within ~5 minutes you may manually withdraw/cancel even while `Pending Approval`.
- **Tracking:** document status codes + approval history visible to requester; buyer can withdraw at any stage.
- URLs: https://docs.oracle.com/en/cloud/saas/procurement/26c/fapra/op-purchaserequisitions-purchaserequisitionsuniqid-child-lines-linesuniqid-action-withdraw-post.html · https://docs.oracle.com/en/cloud/saas/procurement/25d/fapra/op-purchaserequisitions-purchaserequisitionsuniqid-action-withdraw-post.html · https://uchicago.service-now.com/services?id=kb_article&sysparm_article=KB06003676 · https://docs.oracle.com/en/cloud/saas/procurement/25c/oaprc/how-you-resolve-pending-approval-requisitions.html · https://apps2fusion.com/oracle-fusion-procurement-approvals/

### Coupa
- **Status vocabulary:** `First draft, Checked out, Pending Approval, Approved, Ordered, Partially Received, Received, Rejected, Withdrawn, Abandoned, Backgrounded, Buyer/Payment holds` — withdrawal by requester is a first-class trigger event.
- **Submission warnings:** configurable warnings/blocks at submit time (used for approval-chain and policy nudges) — the natural hook point for "you may be duplicating an open request".
- **Fraud/anomaly side (SpendGuard):** detects SPLIT requisitions (self-approval under limit, collusion, threshold-splitting) using addresses, approval chains and timestamps; false-positive filters exclude legitimate recurring orders by role — evidence that "recurring" must be whitelisted in any duplicate heuristic.
- URLs: https://compass.coupa.com/en-us/products/product-documentation/total-spend-management-platform/workflows-and-approvals/process-automator/process-automator-triggers · https://www.coupa.com/blog/managing-purchase-requisitions-spend-guard · https://www.coupa.com/blog/technology-innovation-finding-duplicate-invoices-flight-ai · https://docs.coupa.com/en/developer-documentation/coupa-core-flat-files-csv/flat-file-csv-import/requisitions-import

### Procurify
- **Tracking UX (best-in-class for requesters):** *Order Lifecycle Tracker* — tabbed RFO screen: **Status** (visual 4-stage timeline: Request Submitted → Approval → Purchase(PO link) → Receipt), **Details**, **Audit Trail**. Requesters land on Status; approvers on Details. Linked PO numbers shown to the requester.
- **Templates/recurring:** NO true saved-template object; recurring orders served by a **duplicate/replicate request** function (copy an old request) + blanket POs + subscription tracking.
- **Edit/delete rules by role×status:** requester may DELETE their own PENDING request; approvers cannot delete, only DENY; requests past approvals deletable only under narrow conditions; there are separate guides for editing an APPROVED request and for editing just Account Code/Department/Location of an approved request (field-scoped amendment).
- URLs: https://success.procurify.com/en/articles/9001555-how-to-check-the-status-of-your-request · https://success.procurify.com/en/articles/9001552-requester-basics · https://developer.procurify.com/tag/requisitions/ · https://success.procurify.com/en/articles/9002187-how-to-edit-an-approved-request-for-order

### ServiceNow SPM (Demand Management analog)
- **Duplicate detection mechanics (closest public spec found):** "Identify Similar Demands" button runs semantic-similarity over name/description/business-case against 5 years of history, flags **≥85% similarity**, renders a global alert banner + a "Similar Demands" related list; MANUAL trigger (user-invoked), NEVER auto-merges/closes — a human decides consolidate vs defer.
- Lesson: detection is advisory UI, not enforcement; surfaced at the record, driven off text fields.
- URLs: https://www.servicenow.com/community/spm-articles/identify-demand-duplication-amp-maintain-a-cleaner-demand/ta-p/3495505 · https://www.servicenow.com/docs/r/yokohama/integrate-applications/integration-hub/sap-ariba-spoke.html

### Zycus (iRequest / Merlin Intake)
- Intake-to-Outcomes positioning: conversational/plain-language intake, AI classification, policy checks at the point of request, autonomous routing; e-procurement enforces thresholds/preferred-supplier rules pre-PO. Marketing-level sources; no public duplicate-window spec. Relevant takeaway: checks happen AT INTAKE, before approval.
- URLs: https://www.zycus.com/solution/intake-management · https://dev.zycus.com/freshz/solution/request-management · https://www.zycus.com/solution/procure-to-pay/e-procurement-software

### Kissflow Procurement
- Template-first platform: purchase-request workflow TEMPLATES with budget validation, vendor matching, amount/category routing. **Withdraw:** any submitted item can be withdrawn by the initiator (Process Admin can disable withdrawal per step); withdrawal emails everyone who acted; fresh request started afterwards. Low-code forms capture justification/specifications.
- URLs: https://kissflow.com/templates/procurement/ · https://community.kissflow.com/t/q6h9qtw/editing-a-process-item-after-submitting

### GEP SMART
- Catalog toolkit with catalog templates, favorite shortlists, punch-out, and support for **recurring and pre-specified purchases + blanket orders** at PO level; requisitions electronic for catalog/non-catalog; PO generated directly FROM requisitions with status tracking back.
- URL: https://www.selecthub.com/p/procurement-software/gep-smart

### Jaggaer One
- Guided buying: every request type captured, exceptions visible; budget COMMITTED AT REQUISITION; cost-center split expenses on requisitions; approval routing by value/commodity/BU/cost-center. University training decks show requester-side req→PO status checking and standing orders.
- URLs: https://www.jaggaer.com/solutions/procurement-software · https://www.uh.edu/office-of-finance/purchasing/training-flowcharts/training/jaggaer/

### Ivalua
- Continuous requisition→approval→PO→receipt workflow positioned around preventing duplicate PAYMENTS via full automation + audit trail; configurable data model (no public requisition-amendment spec).
- URLs: https://www.ivalua.com/blog/procurement-automation-software · http://www.ivalua.com/

---

## 2. Deduped Feature Catalog → five 6.2 bullets

| # | Bullet | Industry pattern distilled | Priority |
|---|--------|---------------------------|----------|
| 1 | Requisition Creation | Free-text or catalog lines with qty / required-date / GL-cost coding at LINE level; defaults (dept, currency) prefilled; fast-path entry | **Must** — mostly EXISTS on the scm spine; 6.2 adds template-driven drafting |
| 2 | Requisition Tracking | Requester-facing visual timeline incl. downstream PO linkage; audit trail tab (Procurify model) | **Must** (computed page over spine) |
| 3 | Duplicate Requisition Check | Advisory flag at/near intake, deterministic window + similarity, human decides; whitelist legit recurrence (Coupa/SpendGuard lesson); ServiceNow: manual/visible, never auto-merge | **Must** (explicitly parked to 6.2 in todo.md) |
| 4 | Requisition Templates | Saved reusable blueprints (GEP/Zycus/Kissflow) OR replicate-last-order fallback (Procurify); apply drafts a real requisition | **Must** (parked to 6.2) |
| 5 | Cancellation/Amendment | Status-gated verbs: withdraw (pending) free-ish; cancel (approved) admin-gated + reason; amendments versioned/reasoned, sometimes re-approved (Ariba/Oracle); one-amendment-per-line locking is Later | **Must** (cancel+reason+trail); re-approval loop & line-locking = Later |
| — | Recurrence scheduling (auto-fire templates on a calendar) | GEP/Procurify serve this via blankets/replication, not schedulers | Later |

---

## 3. Prior Art in THIS repo (verified code facts)

### 3.1 Ownership ruling
`.claude/tasks/todo.md` ~L9878: *"SCM 4.1 OWNS the procurement transaction tables (`PurchaseRequisition`, `RFQ`, `PurchaseOrder`, `GoodsReceiptNote` + children). Module 6 … EXTENDS them by string-FK … it must NOT re-declare parallel schema"* (lesson L29). Parking note ~L25865 (6.1 close-out): *"Requisition templates/duplicate detection -> **6.2** owns the requisition UX layer."* Also `apps/procurement/models/_base.py:11-15` repeats L29/L36 ownership.

### 3.2 `scm.PurchaseRequisition` — `apps/scm/models/ProcurementManagement/PurchaseRequisitions.py`
Subclass of `TenantNumbered` (scm `_base`), `NUMBER_PREFIX = "PR"` → numbers `PR-#####`, `unique_together ("tenant","number")`.

Fields (exact):
- `title` CharField(255)
- `requester` FK AUTH_USER_MODEL SET_NULL null blank, `related_name="scm_requisitions"`
- `org_unit` FK `core.OrgUnit` SET_NULL null blank, `related_name="scm_requisitions"` ("requesting department / cost centre — the budget dimension")
- `budget` FK `accounting.Budget` SET_NULL null blank, `related_name="scm_requisitions"`
- `currency` FK `accounting.Currency` SET_NULL null blank, `related_name="scm_requisitions"`
- `required_by` DateField null blank
- `status` CharField(16), `STATUS_CHOICES`: `draft / pending_approval / approved / rejected / converted / cancelled`, default `draft`
- Class tuples: `COMMITTED_STATUSES = ("approved","converted")`; `EDITABLE_STATUSES = ("draft","pending_approval")`; `APPROVAL_TIERS` [(1000,"standard"),(10000,"manager"),(None,"executive")]; `ELEVATED_TIERS = ("manager","executive")`
- `justification` Text blank; `notes` Text blank
- `estimated_total` Dec(18,2) default 0 **editable=False, derived**
- `approved_by` FK user SET_NULL null blank editable=False, `related_name="scm_requisitions_approved"`; `approved_at` DateTime null editable=False; `decision_note` Text blank editable=False
- Indexes: `(tenant,status)` → `scm_pr_tenant_status_idx`; `(tenant,required_by)` → `scm_pr_tenant_reqby_idx`

Methods: `is_editable` (property), `approval_tier()`, `needs_elevated_approval()`, `recalc_totals(save=True)` (sums `lines.line_total`), `budget_check(lines=None)` (view-time compare vs `accounting.BudgetLine`, committed spend summed at LINE level over COMMITTED_STATUSES).

### 3.3 `scm.PurchaseRequisitionLine` (same file)
Plain `models.Model` (**no tenant of its own** — inherits via parent):
- `requisition` FK `scm.PurchaseRequisition` CASCADE, `related_name="lines"`
- `item_description` CharField(255); `sku_hint` Char(64) blank; `uom_hint` Char(32) blank
- `quantity` Dec(14,4) default 1, Min 0.0001; `estimated_unit_price` Dec(14,2) default 0, Min 0; `line_total` Dec(18,2) derived in `save()` (= qty × price)
- `gl_account` FK `accounting.GLAccount` SET_NULL null blank, `related_name="scm_requisition_lines"` ("Expense account to charge")
- `needed_by` DateField null blank; `Meta.ordering=["id"]`

### 3.4 Lifecycle verbs — `apps/scm/views/ProcurementManagement/PurchaseRequisitions.py`
Routes (`apps/scm/urls/ProcurementManagement/PurchaseRequisitions.py`): `requisition_list/create/detail/edit/delete/submit/approve/reject`.
- Create/Edit: form + `PurchaseRequisitionLineFormSet` in `transaction.atomic()`; requester stamped `request.user` on CREATE only; `recalc_totals()` after formset save; audit via `write_audit_log(user, obj, verb, _changed(form))`.
- Edit gate: `is_editable` else error "Only a draft or pending requisition can be edited."
- Delete: POST-only, **draft only**.
- Submit: draft→pending_approval, requires ≥1 line, recalcs first.
- Approve/Reject: `@tenant_admin_required`, pending only; approve stamps approved_by/at + optional note; reject REQUIRES reason into `decision_note`.
- **NO cancel verb exists anywhere for PRs** — `cancelled` is a valid status that NOTHING writes (grep confirms: cancel views exist for POs and GRNs only). This is the concrete gap behind bullet 5.

### 3.5 PR → PO conversion path (indirect, via RFQ award)
`apps/scm/views/ProcurementManagement/Rfqs.py:280-332` `quote_award` (`@tenant_admin_required`): awarded quote → creates **draft** `PurchaseOrder` with `requisition=rfq.requisition`, copies lines, `po.recalc_totals()`; if the source requisition `status=="approved"` it flips to `"converted"`. Links: `RFQ.requisition` FK SET_NULL null (`related_name="rfqs"`); `PurchaseOrder.requisition` FK SET_NULL null (`related_name="purchase_orders"`) at `PurchaseOrders.py:39`. The PR detail template renders both reverse relations ("RFQs raised", "Purchase orders").

### 3.6 6.1 hand-off pattern to reuse — `apps/procurement/views/DashboardPortal/QuickRequisitions.py`
`quickreq_create`: tenant-guard → recent-5 query → on POST builds `PurchaseRequisition` + ONE `PurchaseRequisitionLine` inside `transaction.atomic()`, `requester=request.user` (never choosable), starts `draft`, `needed_by=cleaned["required_by"]`, `req.recalc_totals()`, then `write_audit_log(request.user, req, "create")`, success message with `req.number`, redirect `scm:requisition_detail`. **This exact write shape is the template for template-apply.**

### 3.7 Procurement app toolkit
- `models/_base.py`: abstract `TenantOwned` (tenant FK `related_name="+ db_index=True"`, created_at, updated_at). **No local `TenantNumbered` yet** — scm's numbered base is peer-private, so 6.2 needs its own copy if numbered.
- `forms/_common.py`: `TenantModelForm` (core) + `_reject_foreign(form, cleaned, names)` crafted-POST FK re-check.
- `views/_common.py`: `login_required, messages, get_object_or_404/redirect/render, require_POST`, `crud_create/crud_delete/crud_detail/crud_edit/crud_list` (core.crud), `write_audit_log` (core.utils).
- `views/_helpers.py`: `PROCUREMENT_CONTENT_MODELS = ("purchaserequisition","purchaseorder","goodsreceiptnote","rfq","rfqquote","procurementalert")` whitelist + `procurement_activity_qs(tenant)` builder. New 6.2 models should be appended to the whitelist.
- Migrations present: `0001_initial`, `0002_procurementalert_prc_alr_tnt_sev_idx` → **next is `0003`**.
- `urls/__init__.py` concatenates per-submodule url packages; `app_name="procurement"`.

### 3.8 scm-side PR UI (what 6.2 complements, not duplicates)
`templates/scm/procurement/requisition/{list,detail,form}.html`: status badge colour map; detail shows header grid, lines table (incl. GL account + needed_by), **Budget check card**, RFQs-raised card, POs card, approver's-note card, Actions card (Submit / Approve+note / Reject+reason / Edit-if-editable / Delete-if-draft). List has search + status/org_unit filters + pagination. There is no timeline, no duplicates surface, no templates, no cancel button — those are 6.2's additions.

### 3.9 Seeder facts — `apps/scm/management/commands/seed_scm.py`
Skip-guard per tenant on `PurchaseRequisition.objects.filter(tenant=…).exists()`. Demo PRs: approved "Q3 workstation refresh" (from `REQUISITION_LINES` constant) + pending "Warehouse safety equipment"; helpers `_expense_account(tenant)` (GLAccount `code__startswith="5"` fallback any), `_org_unit`, `_supplier`; ensures a `BudgetLine` (25,000) so budget_check renders meaningfully. `seed_procurement.py` (6.1) currently seeds alerts ONLY and deliberately no requisitions — 6.2 extends THIS command.

### 3.10 Account-code targets (bullet 1)
- `accounting.GLAccount` (`apps/accounting/models/GeneralLedger/GLAccounts.py`): `code`(20)/`name`/`account_type`/`normal_balance`(derived)/`parent`/`is_active`; `unique_together ("tenant","code")`. **Already the PR-line account-code FK** — no new FK needed.
- `core.OrgUnit` — the cost-centre dimension the spine already carries on the header.
- `hrm.CostCenterProfile` exists (HRM 3.2) but is HR-domain; do NOT wire it here.
- `accounting.Budget`/`BudgetLine` — used by `budget_check()`, optional header FK already on the spine.

### 3.11 No prior template/amendment table anywhere
Grep `^class \w*(Template|Amendment)\w*\(` across `apps/*`: hits are CRM (`DocTemplate`, `OnboardingTemplate`, `EmailTemplate`) and HRM (`ReviewTemplate`, `OfferLetterTemplate`, `SalaryStructureTemplate`, `OnboardingTemplate(+Task)`, `CandidateEmailTemplate`, `JobDescriptionTemplate`). **Nothing requisition-related exists; no `RequisitionAmendment`, no duplicate-check model anywhere.** House convention: named `XTemplate(TenantNumbered)` + flat child (`XTemplateTask/LearningPathItem` style, plain Model or TenantOwned, FK `related_name="lines"`/children).

TODO (minor, non-blocking): full body of `templates/scm/procurement/requisition/form.html` and the `REQUISITION_LINES` constant contents were only sampled/grepped, not fully read; `next_number()` implementation site (imported by scm `_base`) not opened — irrelevant to scope since 6.2 copies the proven base pattern.

---

## 4. Recommended Scope

**Ruling honoured:** scm owns the PR status machine; 6.2 adds ZERO columns to scm models. Three new tables in `apps/procurement` + two computed surfaces. Migration **`0003_requisitionmgmt`**.

### 4.1 Models (tables-with-CRUD)

**A. Local numbered base** — copy `TenantNumbered` into `apps/procurement/models/_base.py` (peer apps never import each other's internals; proven scm implementation).

**B. `RequisitionTemplate(TenantNumbered)`** — reusable recurring-order blueprint. `NUMBER_PREFIX="RT"` → `RT-#####`.
- `name` CharField(120) — unique per tenant
- `description` TextField(blank)
- `default_title` CharField(255, blank) — pre-filled requisition title on apply (falls back to name)
- `default_org_unit` FK `core.OrgUnit` SET_NULL null blank, `related_name="procurement_requisition_templates"`
- `default_budget` FK `accounting.Budget` SET_NULL null blank, `related_name="procurement_requisition_templates"`
- `default_currency` FK `accounting.Currency` SET_NULL null blank, `related_name="procurement_requisition_templates"`
- `is_active` Boolean default True — retire-without-delete
- `created_by` FK user SET_NULL null blank editable=False
- `last_applied_at` DateTime null editable=False; `apply_count` PosInt default 0 editable=False
- `unique_together ("tenant","name")`; index `(tenant,is_active)`
- Verb `apply_to(user, *, required_by=None, justification="", notes="") -> scm.PurchaseRequisition`: one `transaction.atomic()` cloning header defaults + `lines` → `scm.PurchaseRequisitionLine`s (mirroring quickreq exactly: status `draft`, requester=user, `needed_by=required_by`, then `recalc_totals()`), bumps counters, returns the PR. **No scheduling/auto-fire** (Later).

**C. `RequisitionTemplateLine(TenantOwned)`**
- `template` FK `RequisitionTemplate` CASCADE, `related_name="lines"`
- `item_description` CharField(255); `sku_hint` Char(64) blank; `uom_hint` Char(32) blank
- `quantity` Dec(14,4) default 1 min 0.0001; `estimated_unit_price` Dec(14,2) default 0 min 0
- `gl_account` FK `accounting.GLAccount` SET_NULL null blank, `related_name="procurement_template_lines"`
- Deliberately NO date field — templates stay evergreen; dates are apply-time inputs.
- Ordering `["id"]`.

**D. `RequisitionAmendment(TenantOwned)`** — append-only trail (table, not bare verbs — justified below).
- `requisition` FK `"scm.PurchaseRequisition"` **PROTECT**, `related_name="procurement_amendments"`
- `action` Char(8) choices `[("cancel","Cancellation"),("amend","Amendment")]`
- `reason` TextField — required at view level (both actions)
- `changed_fields` JSONField default dict, editable=False — `{field_or_line_ref: [old, new]}`
- `requested_by` FK user SET_NULL null editable=False; `applied_by` FK user SET_NULL null editable=False; `applied_at` DateTime auto_now_add editable=False
- Meta: ordering `["-applied_at","-id"]`; index `(tenant, requisition)`. Rows are never edited or deleted (admin.py read-only-ish).
- **Why a table:** the PR spine has NO `version`/`amendment_reason` columns (unlike `PurchaseOrder`, which carries `version`+`amendment_reason` and an admin `purchaseorder_amend` view at `PurchaseOrders.py:96-118` requiring a reason) — and 6.2 must not migrate scm models. `core.AuditLog` diffs exist but scatter across a generic feed; a typed row gives cancel/amend + reason + who-stamped in ONE queryable place and matches the repo's append-only-log idiom (HealthScoreHistory, GoalCheckIn, StockMove).

**Verbs (procurement views writing the scm spine — no fork of approval logic):**
- `cancel`: POST-only. Allowed statuses: `pending_approval` (requester-or-admin; withdraw-equivalent) and `approved` (**tenant_admin_required** — mirrors Ariba Deactivate / Oracle's no-withdraw-once-committed). Refuses `converted` (must cancel the PO via scm's own `purchaseorder_cancel`) and already-`cancelled`. Writes `cancelled` onto the PR (first writer of that status in the system) + amendment row + audit log. Draft stays handled by scm's existing `requisition_delete`.
- `amend`: GET-form/POST on `approved` PRs only, **tenant_admin_required** (PO-precedent gating: an approved PR is committed budget). Header fields (title/justification/required_by/org_unit/budget/notes) + line formset re-opened; reason mandatory; diff captured into `changed_fields`; `recalc_totals()`; PR STAYS `approved` (no re-approval loop in v1 — Ariba/Oracle re-approval = Later; the elevated-tier flag is re-surfaced in the success message). Pending PRs need no amend path — scm's ordinary `requisition_edit` already covers `EDITABLE_STATUSES`.

### 4.2 Computed pages (no storage)

**E. Duplicate detector — pure functions + flags, zero tables.**
Recommended heuristic (deterministic, cheap, tunable constants in one module, e.g. `apps/procurement/views/RequisitionMgmt/_dupes.py`):
```
Candidate pair flagged iff ALL:
  same tenant
  same requester                       (precision-first v1; org_unit variant = Later)
  other.status in OPEN = {draft, pending_approval, approved}
  |created_at difference| <= DUPLICATE_WINDOW_DAYS = 14
  similarity >= 1 of:
    (a) token overlap: >=1 shared alphanumeric token len>=3 (lowercased,
        stopword-free) between ANY pair of line item_descriptions   ← cheap primary
    (b) same dominant gl_account AND totals within 15%              ← catches reworded text
Exclusions: identical requisition; pairs where either came from a template apply
  whose sibling was acknowledged (whitelist recurring demand — Coupa/SpendGuard lesson).
Implementation: ONE indexed query (tenant+requester+status__in+created_at>=window)
  capped at 200 rows + one lines fetch; scoring in Python. No fuzzy libs.
```
Surfaces: (1) warning **after** quickreq/template-apply create via `messages.warning` linking suspected PRs (advisory, never blocks — ServiceNow pattern); (2) a "Possible duplicates" badge column + filterable flag on the tracker page; (3) manual re-check button on tracker (ServiceNow manual-trigger pattern). Never auto-cancels anything.

**F. Requisition Tracker (bullet 2)** — `procurement:requisition_tracker`, computed over the spine: personal-by-default list (mine unless admin widens ?scope=all), status chips, derived 4-stage timeline per PR (Draft → Submitted[created→submitted audit rows] → Decision[approved_by/at] → Ordered[`purchase_orders` + `rfqs` reverse FKs]) — Procurify Lifecycle-Tracker shape, zero new tables.

### 4.3 URL plan (`procurement:<entity>_<verb>`; new package `apps/procurement/urls/RequisitionMgmt/`)
```
requisitiontemplate_list / _create / _detail / _edit / _delete      (CRUD, tenant-scoped)
requisitiontemplate_apply        POST  ?pk= template → drafts spine PR (quickreq mirror)
requisition_tracker              GET   computed tracking + duplicate flags
requisition_duplicate_check      GET   manual re-check (JSON-ish fragment or full page)
requisition_cancel               POST  pk of scm.PR — gated cancel + amendment row
requisition_amend                GET/POST pk of scm.PR — admin amend + amendment row
requisitionamendment_list        GET   filterable (?requisition=<pk> embedded panel)
```

### 4.4 Template plan — `templates/procurement/requisitionmgmt/`
```
requisitiontemplate/list.html  detail.html  form.html
requisition/tracker.html       amend_form.html
partials: dup_banner.html (messages-style suspect list), timeline.html
```
(scm's own requisition pages stay untouched except: none.)

### 4.5 Seeder plan (`seed_procurement` extension, idempotent per-entity guards)
Reuse `seed_scm` fixtures — same tenant's `OrgUnit`, `Currency USD`, expense `GLAccount` (`code startswith 5`), first `Budget` (+ ensure BudgetLine), admin user. Seed: 2 templates ("Monthly office supplies" 3 lines, "Quarterly safety gear" 1 line, GL-coded); 1 applied PR from template A (draft, requester=admin) proving `apply_count=1`; **two deliberate near-duplicates** ("Printer paper — A4 ream" ×60 and "A4 printer paper reams" ×55, same requester/GL, 3 days apart, totals <15% apart, both `pending_approval`) so the detector demonstrably fires on the tracker; 1 amendment row (cancel with reason on a seeded rejected/draft PR is impossible — instead ship one `amend` example only if a seeded approved PR exists, else leave empty). Append `requisitiontemplate`, `requisitiontemplateline`, `requisitionamendment` to `PROCUREMENT_CONTENT_MODELS`.

### 4.6 Tests sketch (for the build pass)
apply clones N lines atomically + counter bump; cancel gates by status×role; converted refused; amend admin-only + reason required + JSON diff; duplicate heuristic truth-table (window edge, token overlap, GL+total branch, template-sibling exclusion, cap); cross-tenant 404s on every verb.

---

## 5. Conflicts found (bullets ↔ scm machinery)

1. **Bullet 5 vs missing verb:** `cancelled` status exists but NO scm view writes it — 6.2 legitimately supplies cancel without touching scm logic (and refuses `converted`, deferring to scm's PO cancel).
2. **Bullet 5 amend-approved:** scm `EDITABLE_STATUSES` hard-blocks approved edits; PO has an admin amend precedent (version+reason) but the PR lacks version columns → external `RequisitionAmendment` table is the only compliant trail.
3. **Bullet 1 account codes:** already structural (`gl_account` FK on lines); 6.2 contributes defaults via templates, not schema.
4. **Bullet 2 tracking:** scm detail already lists RFQs/POs per PR; 6.2's tracker must be the PERSONAL timeline layer, not a second admin list.
5. **Bullet 3:** nothing in scm or procurement touches duplicates — clean greenfield, computed approach preferred (no state to drift).

## 6. Open Questions
1. Should cancelling a `pending_approval` PR notify the would-be approver? (6.3 Approval Workflow Engine will own notifications — defer?)
2. Amend on `approved`: keep total-change ceiling (e.g. refuse >±20% delta forcing cancel+re-raise) or free-form v1?
3. Duplicate window: fixed constant 14 days vs per-tenant setting (no settings singleton exists in procurement yet)?
4. Should `requisitiontemplate_apply` offer quantity-scaling at apply time (×2 months) in v1 or raw clone only?
5. Tracker "Ordered" stage granularity: stop at PO existence (v1) or pull PO status too?
