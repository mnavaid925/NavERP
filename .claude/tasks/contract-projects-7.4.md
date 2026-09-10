# Build Contract — Sub-module 7.4 Cost & Budget Management (Module 7, app `projects`)

> Frozen 2026-09-10 by the SPEC pass from `.claude/tasks/todo.md` L6020–6404,
> `research-projects-7.4.md` (rulings 1–6) and the AS-BUILT code (as-built wins on any conflict —
> see "Contract notes vs plan" at the end). This file is the single source of truth for the
> builder, reviewers and test writers: every model field, CHOICES value, form Meta list, url name,
> path, context key and helper signature below is pinned — an unpinned name renders blank at 200
> or raises `NoReverseMatch`.

## 0. Scope & build order

- **4 models, no fifth**: `BudgetRevision` [BVR-], `CostControlAccount` [CCA-],
  `ProjectBudgetLine` [PBL-], `ProjectExpense` [PEX-]. All `TenantNumbered` subclasses,
  `NUMBER_PREFIX` as bracketed. `unique_together ("tenant","number")` on all four.
- **The cost baseline IS the approved `BudgetRevision`** — never a `CostBaseline`, never `BSL`
  (Ruling 2), no `ChangeRequest` model (Ruling 3). The active baseline is the one row with
  `status="approved"` **and** `activated_at` set — there is **no `is_active` boolean**; uniqueness
  is kept by the `bvr_activate` verb inside `transaction.atomic()` (the `ScheduleBaseline`
  no-conditional-unique precedent).
- **Build order (FK flow, not catalog order)**: BudgetRevision → CostControlAccount →
  ProjectBudgetLine → ProjectExpense. (PBL FKs both BVR and CCA; PEX FKs CCA; BVR/CCA touch only
  the spine.)
- **Ruling 1 (re-checked against `research-projects-7.3.md`, which HAS landed): HOLDS.** 7.4
  stores amounts, never rates/hours. 7.3's research states three times that it ships "NO money
  columns anywhere (no rates, no cost, no billable value)" and parks "Role rate cards — money →
  7.4/7.15 (L29)" in both its bullet-3 catalog and its Deferred table; `ResourceTimeEntry` is
  explicitly "NO billable flag, NO rates, NO money columns". No 7.3 field can collide with a 7.4
  row; a future 7.3 rate card may *generate* `amount`, never add rate fields to it.
- Money = `DecimalField(max_digits=14, decimal_places=2)` through `q2()`/`MAX_Q2`;
  `MinValueValidator(0)` on every amount; **rollups and ALL EVM metrics are computed
  properties/annotations, never stored columns**; audit actions ≤ 10 chars
  (`core.AuditLog.action` is varchar(10)).

## 1. Concurrency preamble (peers 7.2/7.3 live in this tree)

- Every shared-file touch (`models/forms/views/urls __init__.py`, `admin.py`, `seed_projects.py`,
  `apps/core/navigation.py`, `templates/projects/overview.html`, `tests/conftest.py`) is an
  **Integrate-step item**, done once, as a surgical `Edit` with a re-read anchor immediately
  before the edit. Commits are path-limited: `git add '<f>'; git commit -m '<msg>' -- '<f>'`.
- **Models are NOT re-exported from `models/__init__.py` until Integrate.** Entity files may be
  written and `makemigrations --dry-run`-checked, but the app must not import them before the
  re-export block lands.
- **Migration number = the disk leaf at generation time — never reserve `0004`.** Disk today:
  `apps/projects/migrations/` has `0001…0003` only and no `ResourceManagement/` exists in
  `models/ forms/ views/ urls/`; `urls/__init__.py` concatenates only 7.1+7.2 modules. If 7.3
  lands its migration first, 7.4's leaf moves (likely `0005`). **DB-last dry-run registry check:**
  run `python manage.py makemigrations projects --dry-run`, read EVERY model the dry-run lists;
  if it names a model you did not write, STOP and report (7.3 writes models into this same app).
- **Literal-first url segments** `budgetlines/`, `revisions/`, `controlaccounts/`, `expenses/` are
  free today (inventory: `""`, `project-requests/`, `projects/`, `stakeholders/`, `kickoffs/`,
  `tasks/`, `dependencies/`, `milestones/`, `baselines/`). **Re-check the concatenated
  `urls/__init__.py` at Integrate** in case 7.3 added segments.

## 2. Shared toolkit — pinned real signatures (as-built)

| Helper | Location | Signature / behaviour |
|---|---|---|
| `q2(value)` | `apps/projects/models/_base.py:36` | `(value or ZERO)` → clamp to ±`MAX_Q2`, quantize `0.01`. `MAX_Q2 = Decimal("9999999999.99")`, `ZERO = Decimal("0")` |
| `TenantNumbered` | `_base.py:54` | adds `number = CharField(max_length=20, editable=False)`; `save()` retries `next_number(model, tenant, NUMBER_PREFIX)` 5× on `IntegrityError`. `TenantOwned` adds `tenant` FK `core.Tenant` CASCADE `related_name="+"` db_index=True, `created_at` auto_now_add, `updated_at` auto_now |
| `crud_list` | `apps/core/crud.py:115` | `crud_list(request, qs, template, *, search_fields=(), filters=(), extra_context=None, per_page=15)`; `filters` = `(get_param, orm_lookup, is_int)` tuples. Renders `object_list` + `page_obj` + `q` + extras. Windowed pagination (`page.window`), partial `partials/pagination.html` |
| `crud_create` | `crud.py:171` | `crud_create(request, *, form_class, template, success_url, extra_context=None, set_tenant=True, audit=True)`; tenant-less guard first; audit `"create"`; **redirects to `success_url` (a list name — no pk) and has no `created_by` hook**, so 7.4 create views are hand-written (see §9) |
| `crud_edit` | `crud.py:196` | `crud_edit(request, *, model, pk, form_class, template, success_url, extra_context=None, audit=True)`; tenant-scoped `get_object_or_404`; audit `"update"` with `_changed(form)` |
| `crud_detail` | `crud.py:214` | `crud_detail(request, *, model, pk, template, extra_context=None, select_related=())`; renders `obj` |
| `crud_delete` | `crud.py:224` | `crud_delete(request, *, model, pk, success_url, audit=True)`; self-defending POST-only; audit `"delete"` |
| L11 guards | `crud.py` | `as_db_int()` (isdecimal + range + `?x=0` pk-guard) for int FK filters; `_enum_values()` silently IGNORES a `?enum=` value not in the field's CHOICES (default page renders — never a 500, never a silently emptied register). Centralised — views do NOT hand-roll it |
| `tenant_admin_required` | `apps/core/decorators.py:13` | passes when `user.is_superuser or user.is_tenant_admin`, else **raises `PermissionDenied` → 403**. Decorator stack on gated verbs: `@login_required` + `@tenant_admin_required` + `@require_POST` |
| `require_POST` | `django.views.decorators.http` | **GET on any POST-only verb/delete route returns 405** (`HttpResponseNotAllowed`) |
| `write_audit_log` | `apps/core/utils.py:6` | `write_audit_log(user, obj, action, changes=None, tenant=None)`; verb idiom captures `previous = obj.status` BEFORE mutating, then `changes={"verb": ..., "from": previous, "to": obj.status}` (the `prq_*` idiom) |
| `TenantModelForm` | `apps/core/forms/_common.py:25` | `__init__(self, *args, tenant=None, **kwargs)`; auto-scopes every `ModelChoiceField` whose target model HAS a `tenant` field; **skips `accounting.Currency` (no tenant column, L29)**; applies form-select/textarea/input widget classes |
| `TenantUniqueMixin` | `apps/projects/forms/_common.py:31` | stamps `instance.tenant` before `full_clean()` on CREATE + drops `tenant` from unique-validation exclusions. Mix in BEFORE `TenantModelForm` on every 7.4 form |
| `_reject_foreign(form, cleaned, names)` | `forms/_common.py:53` | field-error "That record belongs to another workspace." per chosen FK whose `tenant_id` differs. **Never pass `accounting.Currency`** (would `AttributeError`) |
| `projects(tenant)` | `apps/projects/views/_helpers.py:33` | tenant's Projects ordered by `name`; `.none()` for tenant-less. Reuse for every filter dropdown |

## 3. Model 1 — `BudgetRevision` [BVR-] (`models/CostManagement/BudgetRevisions.py`)

15 declared + 4 inherited = **19 fields**. Realizes bullets 1 (planning document) + 5 (change
control). Inherited: `tenant`, `number`, `created_at`, `updated_at`. `__str__` =
`f"{self.number} — {self.title}"` (idiom).

`STATUS_CHOICES` (`max_length=20`): `draft`/Draft · `pending_approval`/Pending Approval ·
`approved`/Approved · `rejected`/Rejected · `superseded`/Superseded.

| Field | Type + args | null/blank/default | related_name | editable |
|---|---|---|---|---|
| `project` | `FK("projects.Project", CASCADE)` | required | `budget_revisions` | yes |
| `revision_no` | `PositiveSmallIntegerField` | default `0` (0 = the original plan) | — | yes |
| `title` | `CharField(max_length=255)` | required | — | yes |
| `currency` | `FK("accounting.Currency", SET_NULL)` | null, blank | `budget_revisions` | yes |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES)` | default `"draft"` | — | yes (verb-driven; OFF the form) |
| `reason` | `TextField()` | required | — | yes |
| `impact_note` | `TextField()` | blank | — | yes |
| `schedule_impact_note` | `TextField()` | blank | — | yes |
| `requested_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL)` | null, blank | `bvr_requested` | yes (on the form) |
| `requested_at` | `DateTimeField` | null, blank | — | **False** (stamped by `bvr_submit`) |
| `decided_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL)` | null, blank | `bvr_decided` | **False** |
| `decided_at` | `DateTimeField` | null, blank | — | **False** |
| `decision_notes` | `TextField()` | blank | — | yes (model) / **OFF the form** (verb-only evidence) |
| `activated_at` | `DateTimeField` | null, blank | — | **False** (the re-baseline stamp) |
| `created_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL)` | null, blank | `bvr_created` | **False** (stamped in create view) |

- Property `amount_delta` — `q2(SUM(this revision's lines) − SUM(the active revision's lines))`;
  no active revision ⇒ baseline sum is `ZERO`. The approver's headline number.
- `Meta`: `ordering = ["-created_at", "-id"]`; `unique_together = ("tenant","number"),
  ("tenant","project","revision_no")` (two originals is a bug, not a limit); index
  `("tenant","project","status")` → name `bvr_tnt_prj_status_idx`.
- **Refusals**: `status in ("approved", "superseded")` refuses BOTH edit and delete
  (module constant `_LOCKED_MSG`, the `bsl_edit` frozen-row guard; views redirect to detail with
  `messages.error`, write nothing).

### Verbs (all POST-only → 405 on GET; `previous = obj.status` captured before mutating)

| Verb | Gate | Precondition (else) | Transition + stamps | Audit action (≤10) | Redirect |
|---|---|---|---|---|---|
| `bvr_submit` | `@login_required` | `status == "draft"` (else `messages.info` "already …", writes nothing) | → `pending_approval`; `requested_at = timezone.now()` | `submit` | `projects:bvr_detail` |
| `bvr_approve` | `+ @tenant_admin_required` | `status == "pending_approval"` (else `messages.error`) | → `approved`; `decided_by = request.user`, `decided_at = now()`. **Does NOT activate** | `approve` | `projects:bvr_detail` |
| `bvr_reject` | `+ @tenant_admin_required` | `pending_approval`; `BudgetRevisionDecisionForm` must validate (else `messages.error` "A rejection needs a stated reason.") | → `rejected`; `decision_notes = form.cleaned_data["decision_notes"]` + decided stamps | `reject` | `projects:bvr_detail` |
| `bvr_activate` | `+ @tenant_admin_required` | `status == "approved"` (else `messages.error`); already `activated_at` set ⇒ `messages.info` "already the active baseline", writes nothing | Inside `transaction.atomic()`: EVERY other `approved` revision of the project → `superseded` (their `activated_at` kept as history; audit `supersede` per row, changes `{"verb":"supersede","from":"approved","to":"superseded"}`); then `obj.activated_at = now()`, `save(update_fields=["activated_at","updated_at"])` | `activate` | `projects:bvr_detail` |

## 4. Model 2 — `CostControlAccount` [CCA-] (`models/CostManagement/CostControlAccounts.py`)

9 declared + 4 inherited = **13 fields**. Realizes bullets 2 + 4 (Ruling 4). `__str__` =
`f"{self.number} — {self.name}"`.

`STATUS_CHOICES` (`max_length=10`): `planning`/Planning · `active`/Active · `closed`/Closed
(deviation #2 — baseline membership is DERIVED from the active revision, never a status value).

| Field | Type + args | null/blank/default | validators | related_name |
|---|---|---|---|---|
| `project` | `FK("projects.Project", CASCADE)` | required | — | `control_accounts` |
| `name` | `CharField(max_length=255)` | required | — | — |
| `code` | `CharField(max_length=30)` | required (tenant's CA id, e.g. "CA-1.2") | — | — |
| `wbs_node` | `FK("projects.ProjectTask", SET_NULL)` | null, blank | `clean()` same-project guard (the `anchor_task` pattern) | `control_accounts` |
| `gl_account` | `FK("accounting.GLAccount", PROTECT)` | null, blank | never posts (Ruling 6) | `project_control_accounts` |
| `contingency` | `DecimalField(14,2)` | default `0` | `MinValueValidator(0)`; sized by 7.5, recorded here (Ruling 6) | — |
| `percent_complete` | `DecimalField(5,2)` | default `0` | `MinValueValidator(0)`, `MaxValueValidator(100)`; manually attested — **docstring MUST name the 7.8 hand-off** (execution fields supersede it) | — |
| `status` | `CharField(max_length=10, choices=STATUS_CHOICES)` | default `"planning"` | on the form (no verbs exist) | — |
| `note` | `TextField()` | blank | — | — |

### Derived properties (ALL guarded, ALL Decimal, NEVER columns; money q2()-clamped)

- `active_revision` — `self.project.budget_revisions.filter(status="approved",
  activated_at__isnull=False).order_by("-activated_at").first()`; `None` when none.
- `bac` — SUM of the **active** revision's `ProjectBudgetLine.amount` where `control_account=self`;
  `0` when no active revision. `bac_with_contingency` = `q2(bac + contingency)` (PMBOK keeps them
  separable).
- `ev` = `q2(bac × percent_complete / 100)`.
- `pv` = `q2(bac × fraction)`; fraction = linear elapsed of the anchored node's
  (`wbs_node.planned_start/planned_end`) else the project's (`start_date/end_date`) window at
  `timezone.localdate()`; `0` before start, `1` after finish, `0` when no valid window;
  **docstring states this is planning-grade, not a time-phased BCWS curve** (the
  `critical_path_ids` honesty precedent).
- `ac` — SUM of `ProjectExpense.amount` where `control_account=self, status="posted",
  entry_type in ("actual","accrual")`; `committed` — same aggregate with
  `entry_type="commitment"`; `available` = `q2(bac − committed − ac)`.
- `cv = q2(ev − ac)`; `sv = q2(ev − pv)`; `cpi = ev/ac` → **None when `ac == 0`**; `spi = ev/pv`
  → **None when `pv == 0`**; `eac = q2(bac/cpi)` when `cpi` else `q2(bac)` (one documented
  technique, no method selector); `etc = q2(eac − ac)`; `tcpi = q2((bac − ev)/(bac − ac))` →
  **None when `(bac − ac) == 0`**; `vac = q2(bac − eac)`.
- `health` → dict `{"state": "under"|"watch"|"over", "badge":
  "badge-green"|"badge-amber"|"badge-red"}` (colour-named classes only — the semantic variants do
  not exist). Cut-points (deviation #5): **over** = `available < 0` OR (`cpi is not None` and
  `cpi < 0.95`); **watch** = `cpi is not None and cpi < 1.00`; else **under**. (`cpi is None` ⇒
  no actuals — never "over" by CPI alone.)
- `Meta`: `ordering = ["-created_at","-id"]`; `unique_together = ("tenant","number"),
  ("tenant","project","code")`; indexes `("tenant","project")` → `cca_tnt_project_idx`,
  `("tenant","status")` → `cca_tnt_status_idx`.
- **No verbs** — the register is read + CRUD. `clean()` also validates
  `wbs_node.project_id == project_id`.

## 5. Model 3 — `ProjectBudgetLine` [PBL-] (`models/CostManagement/ProjectBudgetLines.py`)

8 declared + 4 inherited = **12 fields** (the plan's "9 declared" header count is stale — see
Contract notes). The row the whole sub-module rolls up from. **No `hours`, no `rate`** (Ruling 1).
`__str__` = `f"{self.number} — {self.get_category_display()} {self.amount}"` shape permitted;
minimum `f"{self.number} — {self.project}"`.

`CATEGORY_CHOICES` (`max_length=14`, **no default** — a required choice on the form):
`labor`/Labor · `material`/Material · `equipment`/Equipment · `subcontract`/Subcontract ·
`overhead`/Overhead · `contingency`/Contingency · `other`/Other.

| Field | Type + args | null/blank/default | validators | related_name |
|---|---|---|---|---|
| `budget_revision` | `FK(BudgetRevision, CASCADE)` | required (the line is only real inside a revision) | — | `lines` |
| `project` | `FK("projects.Project", CASCADE)` | required (denormalised for filters) | `clean()`: must equal the revision's project | `budget_lines` |
| `category` | `CharField(max_length=14, choices=CATEGORY_CHOICES)` | required, no default | — | — |
| `wbs_node` | `FK("projects.ProjectTask", SET_NULL)` | null, blank | `clean()`: `wbs_node.project` == `project` | `budget_lines` |
| `control_account` | `FK(CostControlAccount, SET_NULL)` | null, blank | `clean()`: `control_account.project` == `project` | `budget_lines` |
| `gl_account` | `FK("accounting.GLAccount", PROTECT)` | null, blank | — | `project_budget_lines` |
| `amount` | `DecimalField(14,2)` | required | `MinValueValidator(0)` | — |
| `note` | `TextField()` | blank | — | — |

- View-level derived ONLY (annotations/`Sum`, never columns): category totals, project total,
  per-CA BAC.
- `Meta`: `ordering = ["-created_at","-id"]`; `unique_together = ("tenant","number")`; indexes
  `("tenant","project")` → `pbl_tnt_project_idx`, `("tenant","budget_revision")` →
  `pbl_tnt_rev_idx`, `("tenant","control_account")` → `pbl_tnt_ca_idx`.
- No verbs. Ordinary frozen-free CRUD on unlocked rows — **close-out ruling (I1, 2026-09-10):**
  `pbl_edit`/`pbl_delete` refuse when the parent `budget_revision.is_locked` (approved/superseded),
  the same frozen-history guard BVR rows carry ("its lines cannot be edited or deleted; submit a
  new revision to change the baseline"); the correction path is a new revision.

## 6. Model 4 — `ProjectExpense` [PEX-] (`models/CostManagement/ProjectExpenses.py`)

14 declared + 4 inherited = **18 fields** (plan's "13 declared" count is stale — see Contract
notes). Realizes bullet 3; feeds `ac`/`committed`. `__str__` = `f"{self.number} —
{self.get_entry_type_display()} {self.amount}"` shape.

- `ENTRY_TYPE_CHOICES` (`max_length=10`, default `actual`): `commitment`/Commitment ·
  `actual`/Actual · `accrual`/Accrual.
- `SOURCE_KIND_CHOICES` (`max_length=15`, default `manual` — deviation #4): `purchase_order`/
  Purchase Order · `supplier_invoice`/Supplier Invoice · `contract`/Contract · `timesheet`/
  Timesheet · `manual`/Manual · `accrual`/Accrual.
- `STATUS_CHOICES` (`max_length=6`, default `draft`, **verb-driven, NOT on form**): `draft`/Draft
  · `posted`/Posted · `void`/Void.

| Field | Type + args | null/blank/default | validators | related_name |
|---|---|---|---|---|
| `project` | `FK("projects.Project", CASCADE)` | required | `clean()`: FKs same-project | `expenses` |
| `control_account` | `FK(CostControlAccount, PROTECT)` | **required, non-nullable** — a CA-less cost row would silently drop out of every index | — | `expenses` |
| `wbs_node` | `FK("projects.ProjectTask", SET_NULL)` | null, blank | `clean()`: same-project | `expenses` |
| `entry_type` | `CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)` | default `"actual"` | — | — |
| `source_kind` | `CharField(max_length=15, choices=SOURCE_KIND_CHOICES)` | default `"manual"` | — | — |
| `source_number` | `CharField(max_length=30)` | blank | **soft reference, NEVER an FK** (Ruling 5 — e.g. `PO-00042`, `SIV-00187`) | — |
| `vendor` | `FK("core.Party", SET_NULL)` | null, blank | — | `project_expenses` |
| `gl_account` | `FK("accounting.GLAccount", PROTECT)` | null, blank | — | `project_expenses` |
| `amount` | `DecimalField(14,2)` | required | `MinValueValidator(0)`; reversals are paired void/adjustment rows, not negatives | — |
| `currency` | `FK("accounting.Currency", SET_NULL)` | null, blank | — | `project_expenses` |
| `entry_date` | `DateField()` | **required, non-nullable** (deviation #4; the burn-trend dimension) | — | — |
| `status` | `CharField(max_length=6, choices=STATUS_CHOICES)` | default `"draft"` | verb-driven; OFF the form | — |
| `description` | `CharField(max_length=255)` | blank | — | — |
| `created_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL)` | null, blank | — | `pex_created` |

- Burn trend = aggregation over `entry_date` in the views — **no snapshot table**; charts are
  7.16's.
- `Meta`: `ordering = ["-entry_date", "-id"]`; `unique_together = ("tenant","number")`; indexes
  `("tenant","project")` → `pex_tnt_project_idx`, `("tenant","control_account")` →
  `pex_tnt_ca_idx`, `("tenant","entry_type")` → `pex_tnt_etype_idx`, `("tenant","entry_date")` →
  `pex_tnt_date_idx`.

### Verbs (POST-only → 405 on GET)

| Verb | Gate | Precondition (else) | Transition | Audit | Redirect |
|---|---|---|---|---|---|
| `pex_post` | `@login_required` | `status == "draft"` (posted ⇒ `messages.info` "already posted"; void ⇒ `messages.error`) | → `posted`. Drafts never burn budget | `post` | `projects:pex_detail` |
| `pex_void` | `+ @tenant_admin_required` | `status == "posted"` (draft ⇒ `messages.error` "Only a posted expense can be voided"; void ⇒ `messages.info`) | → `void`. Void rows stay visible and stop counting | `void` | `projects:pex_detail` |

- **Refusals (deviation #3)**: `pex_edit`/`pex_delete` refuse `status in ("posted","void")` —
  posted cost rows are the evidence the EVM math reads; `pex_void` is the correction path.

## 7. Forms (`forms/CostManagement/<Entity>.py`; base `TenantUniqueMixin, TenantModelForm` on all four)

| Form | Meta `fields` (declared, whitelist) | Excluded (both directions stated) | `_reject_foreign` list | Notes |
|---|---|---|---|---|
| `BudgetRevisionForm` | `["project","revision_no","title","currency","reason","impact_note","schedule_impact_note","requested_by"]` | `tenant`, `number`, `status`, `requested_at`, `decided_by`, `decided_at`, `decision_notes`, `activated_at`, `created_by` (+ non-editable `created_at`/`updated_at` are never form fields) | `["project","requested_by"]` | `currency` unscoped (L29 — `TenantModelForm` auto-skips, `_reject_foreign` never sees it) |
| `BudgetRevisionDecisionForm(forms.Form)` | field `decision_notes` = `forms.CharField(widget=forms.Textarea(attrs={"class":"form-textarea","rows":3}), required=True, label="Reason")` | — (plain `forms.Form`, not a ModelForm) | — | The `ProjectRequestDecisionForm` mirror (shape from as-built, field name = the model column); used ONLY by `bvr_reject` |
| `CostControlAccountForm` | `["project","name","code","wbs_node","gl_account","contingency","percent_complete","status","note"]` | `tenant`, `number` | `["project","wbs_node","gl_account"]` | `status` IS on this form (CCA has no verbs) |
| `ProjectBudgetLineForm` | `["budget_revision","project","category","wbs_node","control_account","gl_account","amount","note"]` | `tenant`, `number` | `["budget_revision","project","wbs_node","control_account","gl_account"]` | model `clean()` re-checks revision/wbs/CA same-project on POST |
| `ProjectExpenseForm` | `["project","control_account","wbs_node","entry_type","source_kind","source_number","vendor","gl_account","amount","currency","entry_date","description"]` | `tenant`, `number`, `status`, `created_by` | `["project","control_account","wbs_node","vendor","gl_account"]` | `currency` unscoped (L29); `currency` initial = the project's active revision's currency, else the tenant's first Currency (supplied by the create view) |

Tenant-scoped querysets: every `ModelChoiceField` above is auto-scoped by `TenantModelForm`
(target model has `tenant`), including `requested_by`/`vendor` (both tenant-carrying). Only
`currency` stays unscoped. `_reject_foreign` still re-checks on POST (a narrowed `<select>` is
UX, not an authorization boundary).

## 8. URLs (`urls/CostManagement/<Entity>.py`; `app_name = "projects"` set ONCE in `urls/__init__.py`; literal routes before `<int:pk>/`)

| Entity (prefix) | url name → path | Methods |
|---|---|---|
| ProjectBudgetLine (`budgetlines/`) | `pbl_list` → `budgetlines/` · `pbl_create` → `budgetlines/add/` · `pbl_detail` → `budgetlines/<int:pk>/` · `pbl_edit` → `budgetlines/<int:pk>/edit/` · `pbl_delete` → `budgetlines/<int:pk>/delete/` | list/detail GET; create/edit GET+POST; delete POST-only (405 on GET) |
| BudgetRevision (`revisions/`) | `bvr_list` → `revisions/` · `bvr_create` → `revisions/add/` · `bvr_detail` → `revisions/<int:pk>/` · `bvr_edit` → `revisions/<int:pk>/edit/` · `bvr_delete` → `revisions/<int:pk>/delete/` · `bvr_submit` → `revisions/<int:pk>/submit/` · `bvr_approve` → `revisions/<int:pk>/approve/` · `bvr_reject` → `revisions/<int:pk>/reject/` · `bvr_activate` → `revisions/<int:pk>/activate/` | pages GET(+POST for create/edit); ALL verbs POST-only → **405 on GET** |
| CostControlAccount (`controlaccounts/`) | `cca_list` → `controlaccounts/` · `cca_create` → `controlaccounts/add/` · `cca_detail` → `controlaccounts/<int:pk>/` · `cca_edit` → `controlaccounts/<int:pk>/edit/` · `cca_delete` → `controlaccounts/<int:pk>/delete/` | as PBL; no verbs |
| ProjectExpense (`expenses/`) | `pex_list` → `expenses/` · `pex_create` → `expenses/add/` · `pex_detail` → `expenses/<int:pk>/` · `pex_edit` → `expenses/<int:pk>/edit/` · `pex_delete` → `expenses/<int:pk>/delete/` · `pex_post` → `expenses/<int:pk>/post/` · `pex_void` → `expenses/<int:pk>/void/` | verbs POST-only → 405 on GET |

Each module: `urlpatterns = [...]` importing `from apps.projects import views`, no `app_name`.
Integrate appends to `urls/__init__.py`: `from .CostManagement.BudgetRevisions import urlpatterns
as _cm_budgetrevisions` (+ `CostControlAccounts` → `_cm_controlaccounts`, `ProjectBudgetLines` →
`_cm_budgetlines`, `ProjectExpenses` → `_cm_expenses`) and `+ _cm_budgetlines +
_cm_controlaccounts + _cm_budgetrevisions + _cm_expenses` with a `# 7.4 …` comment.

## 9. Views (`views/CostManagement/<Entity>.py`)

Common to every view: queryset `filter(tenant=request.tenant)`, never `.all()`; every `<int:pk>`
fetch is tenant-scoped `get_object_or_404` (cross-tenant ID → 404); create views are hand-written
`prq_create`/`bsl_create` wrappers (first line `if request.tenant is None: messages.error(...)
→ redirect("dashboard:home")`; stamp `created_by` on BVR/PEX; `initial={"project":
request.GET.get("project","")}`; audit `"create"`; `messages.success(f"… {obj.number} created.")`;
redirect to the entity's `*_detail`) because `crud_create` has no `created_by` hook and cannot
redirect to a pk detail. Edit/delete/`crud_detail` may delegate to the helpers after the frozen
refusal guard. Form pages render `form` + `is_edit`; edit pages also carry `obj`.

### Registers — filters (param → lookup, is_int) and EXACT context keys

| View | filters | search_fields | Extra context keys (beyond `object_list`/`page_obj`/`q`) |
|---|---|---|---|
| `pbl_list` | `("project","project_id",True)` · `("budget_revision","budget_revision_id",True)` · `("category","category",False)` · `("control_account","control_account_id",True)` | `["number","note"]` | `projects`, `revisions` (tenant's BudgetRevisions), `category_choices` (`ProjectBudgetLine.CATEGORY_CHOICES`), `control_accounts`, `category_totals` (dict `{category_value: Decimal Sum}` over the filtered queryset), `grand_total` (Sum over the same scope) |
| `bvr_list` | `("project","project_id",True)` · `("status","status",False)` | `["number","title","reason"]` | `projects`, `status_choices` (`BudgetRevision.STATUS_CHOICES`) |
| `cca_list` | `("project","project_id",True)` · `("status","status",False)` | `["number","name","code","note"]` | `projects`, `status_choices` (`CostControlAccount.STATUS_CHOICES`); each row renders `obj.health.badge` + `obj.cpi` |
| `pex_list` | `("project","project_id",True)` · `("entry_type","entry_type",False)` · `("status","status",False)` · `("control_account","control_account_id",True)` | `["number","description","source_number"]` | `projects`, `entry_type_choices`, `status_choices`, `source_kind_choices`, `control_accounts` |

Invalid GET values: junk enum / `?project=0` / over-range int / `?page=9999` are silently IGNORED
by the `crud_list` guards — default page renders, never a 500, never a silently emptied register.

### Detail pages — EXACT context keys

| View | Context keys |
|---|---|
| `bvr_detail` | `obj`, `lines` (the revision's `obj.lines.all`), `category_totals` (dict over `lines`); `obj.amount_delta` rendered as the approver's headline (property, no extra key) |
| `cca_detail` | `obj` (the EVM panel reads `obj.bac/bac_with_contingency/ev/pv/ac/committed/available/cv/sv/cpi/spi/eac/etc/tcpi/vac/health` straight off the properties — NO computed context keys), `budget_lines` (the active revision's `ProjectBudgetLine` rows mapped to this CA), `expenses` (recent `posted` rows for this CA, `-entry_date`, capped `[:25]`) |
| `pbl_detail`, `pex_detail` | `obj` (plain render, the `bsl_detail` idiom) |

### Verb behaviour (pinned)

- Every verb: tenant-scoped fetch → precondition check → **`previous = obj.status` BEFORE
  mutating** → mutate (+stamps) → `write_audit_log(request.user, obj, "<action>",
  changes={"verb": <verb>, "from": previous, "to": obj.status})` → `messages.success` →
  redirect to the entity's `*_detail`. An action already in its target state says so
  (`messages.info`) and writes nothing; a disallowed transition is `messages.error` and writes
  nothing. Gates + transitions + audit actions per the tables in §3/§6. Gating decorator stack:
  `@login_required`, then `@tenant_admin_required` (403 for members), then `@require_POST`
  (405 for GET) — the `bsl_activate` order.
- `bvr_activate` writes ONE extra `supersede` audit row per superseded revision (inside the same
  `transaction.atomic()`).

## 10. Templates (`templates/projects/cost/<entity>/{list,detail,form}.html`; entity folders lowercase singular)

All 12 pages: `{% extends "base.html" %}` unchanged; blocks `title` + `content`; breadcrumb to
`projects:overview`; list pages carry the filter-bar `<form method="get" class="filter-bar">`
reflecting `request.GET` (`{% if request.GET.<param> == p.pk|stringformat:"d" %}selected{% endif %}`
for FK selects, direct `==` for enums), table + Actions column, `{% include
"partials/pagination.html" %}` with `has_previous`/`has_next` guards, `{% empty %}` fallback
row, and delete-POST buttons with `onsubmit="return confirm('…');"` + `{% csrf_token %}`.
**No nullable FK inside a `|default:` filter argument** (the 7.1 four-500 idiom) — use
`{% if %}…{% else %}—{% endif %}`. FK `<select>` comparisons use `|stringformat:"d"`. Every
badge block ends `{% else %}<span class="badge">{{
obj.get_<field>_display }}</span>{% endif %}` (colour-named classes only).

| Page | Distinct contents |
|---|---|
| `budgetrevision/list.html` | status badge incl. `superseded` (map: draft→`badge-slate`, pending_approval→`badge-amber`, approved→`badge-green`, rejected→`badge-red`, superseded→`badge-info`; fallback `get_status_display`); filters `q/project/status` |
| `budgetrevision/detail.html` | line table with category totals, the `amount_delta` headline, verb buttons gated by status AND admin (`{% if request.user.is_superuser or request.user.is_tenant_admin %}` — the `bsl_detail` comment+guard idiom): Submit (draft), Approve/Reject (pending_approval, reject posts `BudgetRevisionDecisionForm`'s `decision_notes` textarea), Activate (approved, not yet `activated_at`); Edit/Delete only when `status not in approved/superseded` |
| `costcontrolaccount/list.html` | health badge column `<span class="badge {{ obj.health.badge }}">{{ obj.health.state }}</span>` + `cpi` per row (render `—` when `cpi is None`); filters `q/project/status` |
| `costcontrolaccount/detail.html` | the EVM panel rows: BAC, BAC + contingency, EV, PV (caption "planning-grade linear PV — not a time-phased BCWS curve"), AC, committed, available, CV, SV, CPI, SPI, EAC, ETC, TCPI, VAC + the health badge; then the CA's `budget_lines` table and its `expenses` (posted, capped 25) |
| `projectbudgetline/{list,detail,form}.html` | list filters `q/project/budget_revision/category/control_account` + totals strip (`category_totals`/`grand_total`); Actions column view/edit/delete |
| `projectexpense/{list,detail,form}.html` | list filters `q/project/entry_type/status/control_account`; Actions column adds Post (draft) / Void (posted, admin-gated) per status; detail shows source_kind/source_number soft reference |

## 11. Integrate contract (single writer — the ONLY shared-file step; surgical `Edit`, re-read anchors)

1. **Re-export blocks** `# --- 7.4 Cost & Budget Management ---` appended to all four top-level
   `__init__.py` (a missing re-export is a runtime `ImportError`):
   - `models/__init__.py`: `from .CostManagement.BudgetRevisions import BudgetRevision` ·
     `from .CostManagement.CostControlAccounts import CostControlAccount` ·
     `from .CostManagement.ProjectBudgetLines import ProjectBudgetLine` ·
     `from .CostManagement.ProjectExpenses import ProjectExpense` (each `# noqa: F401`).
   - `forms/__init__.py`: `BudgetRevisionForm`, `BudgetRevisionDecisionForm` (tuple import),
     `CostControlAccountForm`, `ProjectBudgetLineForm`, `ProjectExpenseForm` — **5 forms**.
   - `views/__init__.py`: **26 names** — `bvr_list, bvr_create, bvr_detail, bvr_edit, bvr_delete,
     bvr_submit, bvr_approve, bvr_reject, bvr_activate` · `cca_list, cca_create, cca_detail,
     cca_edit, cca_delete` · `pbl_list, pbl_create, pbl_detail, pbl_edit, pbl_delete` ·
     `pex_list, pex_create, pex_detail, pex_edit, pex_delete, pex_post, pex_void`.
   - `urls/__init__.py`: 4 urlpatterns imports + concat (§8).
2. **`admin.py`** — 4 registrations appended after the 7.2 block, `list_display` led by `number`,
   `list_select_related` for every rendered FK, stamps readonly:
   `BudgetRevisionAdmin` (`("number","title","project","revision_no","status","requested_at",
   "decided_at","tenant")`, select_related `("tenant","project")`, readonly
   `("created_at","updated_at","created_by","requested_at","decided_by","decided_at",
   "activated_at")`); `CostControlAccountAdmin` (`("number","code","name","project","wbs_node",
   "status","percent_complete","tenant")`, select_related `("tenant","project","wbs_node")`);
   `ProjectBudgetLineAdmin` (`("number","budget_revision","project","category","control_account",
   "amount","tenant")`, select_related `("tenant","budget_revision","project","wbs_node",
   "control_account")`); `ProjectExpenseAdmin` (`("number","project","control_account",
   "entry_type","source_kind","source_number","amount","entry_date","status","tenant")`,
   select_related `("tenant","project","control_account")`, readonly incl. `created_by`).
3. **`seed_projects.py`** — `_cost(self, tenant, now)` block with its OWN guard
   `BudgetRevision.objects.filter(tenant=tenant).exists()` (message "cost rows already exist. Use
   --flush to re-seed."), called per tenant after `self._planning(tenant, now)`, inside
   `transaction.atomic()`, constructing rows individually (NEVER `bulk_create` — `TenantNumbered`
   numbering). Per tenant: revision 0 (`approved` + `activated_at` stamped) per seeded project
   with **7–10 PBL lines across all categories** anchored to the existing WBS work packages; one
   CA per deliverable of the ACTIVE project with `percent_complete` values landing CPI in all
   three health bands; ~12 `ProjectExpense` rows (commitments with `source_number="PO-…"`
   **strings only** — `scm.PurchaseOrder` rows are not guaranteed; actuals + one accrual pair);
   one `pending_approval` revision with a visible positive `amount_delta`. Enough PBL rows for
   page 2 (3 projects × ~8 = 24 > 15). `--flush` deletes children-FIRST — prepend
   `ProjectExpense.objects.all().delete()`, `ProjectBudgetLine…`, `CostControlAccount…`,
   `BudgetRevision…` at the top of the flush block (before `ScheduleBaseline`).
4. **`apps/core/navigation.py`** — one new `LIVE_LINKS["7.4"]` immediately after the `"7.2"`
   block (~`:1729`), verbatim:
   ```python
   "7.4": {
       "Budget Planning & Estimation":      "projects:pbl_list",
       "Cost Baseline & Control Accounts":  "projects:cca_list",
       "Expense Tracking & Commitments":    "projects:pex_list",
       "Forecasting & EAC":                 "projects:cca_list",   # EAC/CPI/SPI/TCPI/VAC render on the CA register + detail
       "Change Control & Budget Revisions": "projects:bvr_list",
       # Extra live leaf: the flat register behind the WBS-anchored budget (7.2's "Task Register"
       # precedent). Bullet 4 maps to the same register as bullet 2 on purpose — the EVM columns
       # are CA columns, and a bullet may be a lens on a register rather than a new page.
       "Budget Register":                   "projects:pbl_list",
   },
   ```
   (comment records the deliberate lens-mapping).
5. **`templates/projects/overview.html`** + `views/ProjectInitiation/Overview.py` — 7.4 quick
   links + counts mirroring the 7.2 block: two new context keys **`pending_revisions`**
   (BudgetRevision `status="pending_approval"` count) and **`posted_spend`** (Sum of posted
   actual/accrual `ProjectExpense.amount`, one aggregate each — the "ONE aggregate per TABLE"
   idiom) rendered as two new stat-cards, plus "Cost & Budget" rows (Budget Register, Budget
   Revisions, Control Accounts, Expenses) in the "Start here" table.
6. **DB LAST**: `python manage.py makemigrations projects --dry-run` — read every model the
   dry-run lists; **if it names a model you did not write, STOP and report** (7.3 writes models
   into this same app). Then generate (number = disk leaf), `migrate`, `seed_projects` ×2 (second
   run a no-op), `manage.py check`.

## 12. Test-phase names (names only — contents are the test writer's)

Conftest precedent (`apps/projects/tests/conftest.py`): root conftest already provides
`tenant_a/tenant_b/admin_user/member_user/admin_b/client_a/client_b/member_client`; 7.4 appends
per-subslug names — fixtures `cost_*`, module-level factory helpers `_cost_*`, page-size constant
`COST_PAGE_SIZE = 15`. Fixtures to expect (~14 + lifecycle set):

- Spine: `cost_currency` (global USD, `get_or_create` — L29), `cost_gl_account_a`/`cost_gl_account_b`,
  `cost_party_a`/`cost_party_b` (vendor), `cost_project_a`/`cost_project_b`, `cost_wbs_node_a`/
  `cost_wbs_node_b` (ProjectTask work package).
- Actors mirroring 7.1: `cost_member_b`, `cost_tenantless_user`, `cost_tenantless_client`,
  `cost_anon_client`, `cost_csrf_client`.
- Lifecycle (one fixture per state the verbs branch on): `cost_revision_draft`,
  `cost_revision_pending`, `cost_revision_approved`, `cost_revision_rejected`,
  `cost_revision_superseded`, `cost_revision_b`; `cost_control_account_a` (+ one per health band),
  `cost_control_account_b`; `cost_budget_line_a`; `cost_expense_draft`, `cost_expense_posted`,
  `cost_expense_void`, `cost_expense_b`.
- Helpers: `_cost_revision`, `_cost_control_account`, `_cost_budget_line`, `_cost_expense`,
  `_cost_fill_*`; test modules `test_cost_models.py` → `test_cost_forms.py` →
  `test_cost_views.py` → `test_cost_security.py`; test functions `test_cost_*`. No shadowing of
  the `projectinitiation_*` namespace.

## 13. Pinned deviations (verbatim from the todo plan)

1. **`BudgetRevision.decision_notes` is ADDED** — bullet 5's "rejection with a reason" row names
   it, but the sketch's field list omits it.
2. **`CostControlAccount.status` collapses to `planning/active/closed`** (sketch says four values
   then its own "keep it simple" parenthetical says leave it to planning/closed) — baseline
   membership is *derived* from the active revision, never a status value.
3. **`pex_edit`/`pex_delete` refuse `posted`/`void` rows** — posted cost rows are the evidence the
   EVM math reads; `pex_void` is the correction path (7.1's evidence model; the sketch only fixes
   edit refusal for approved revisions).
4. **`entry_date` pinned non-nullable and `source_kind` defaults to `manual`** — pins of values
   the sketch left unstated (a burn-trend row without a date is meaningless; manual is the only
   kind that needs no source document).
5. **Health cut-points pinned**: `over` = `cpi < 0.95` or `available < 0`, `watch` = `cpi < 1.00`
   — the sketch names the bands but not the numbers.

## 14. Contract notes vs plan (as-built wins; differences found while pinning)

1. **Crud helpers**: the plan says "full CRUD via the `crud_*` helpers" — the real set is
   `crud_list/crud_create/crud_edit/crud_detail/crud_delete` in **`apps/core/crud.py`** (not
   `apps/projects`), imported via `apps/projects/views/_common.py`. `crud_create` has no
   `created_by` hook and redirects to a pk-less `success_url`, so the four create views are
   hand-written wrappers (the `prq_create`/`bsl_create` idiom), as pinned in §9.
2. **Enum allow-list (L11)** is centralised inside `crud_list` (`_enum_values` + `as_db_int`
   + the `?x=0` pk-guard) — views declare `filters` tuples and do NOT hand-roll allow-listing,
   which is what the plan's "every `?enum=` value allow-listed" bullet could be read to require.
3. **Gating helper**: real name is `tenant_admin_required` (`apps/core/decorators.py`) — raises
   `PermissionDenied` → 403 for `not (is_superuser or is_tenant_admin)`. Matches the plan's
   "tenant_admin" wording; the mechanism is now pinned.
4. **GET on verbs**: the plan's verify step expects 405 — confirmed: every verb/delete view is
   `@require_POST`, so GET returns `HttpResponseNotAllowed` (405). `crud_delete` additionally
   self-defends on POST.
5. **Stale field counts in the plan headers**: BVR says "14 declared + 4 = 18" but deviation #1
   adds `decision_notes` → **15 + 4 = 19**; PBL says "9 declared + 4 = 13" but its own field list
   has **8 + 4 = 12**; PEX says "13 declared + 4 = 17" but its list has **14 + 4 = 18**. The §3–§6
   tables are authoritative.
6. **`BudgetRevisionDecisionForm`**: the plan's shorthand "(decision_notes Textarea, required)"
   vs the as-built mirror `ProjectRequestDecisionForm` (a plain `forms.Form` with a `reason`
   field). Pinned: plain `forms.Form`, single required Textarea **named `decision_notes`** (field
   name from the plan's column, shape from the mirror); `bvr_reject` writes
   `form.cleaned_data["decision_notes"]` into `obj.decision_notes`.
7. **Fixture namespace**: the todo says "no shadowing of the `test_initiation_*` namespace" — the
   conftest's actual prefix is `projectinitiation_*` (and 7.2 has appended no `planning_*`
   fixtures yet; 7.2 is in review). `cost_*` is collision-free either way.
8. **`currency` related_name**: the plan leaves it unstated; the 7.1 precedent
   (`ProjectRequest.currency`, `related_name="project_requests"`) names its reverses, so pinned:
   BVR → `budget_revisions`, PEX → `project_expenses`.
9. **Context keys the plan described but did not name** (pinned here per L7): `cca_detail` →
   `budget_lines`, `expenses`; `bvr_detail` → `category_totals`; `pbl_list` → `category_totals`,
   `grand_total`; `health` dict shape → `{"state", "badge"}`; overview → `pending_revisions`,
   `posted_spend`.
10. **Audit `changes` shape**: `bsl_activate` logs `{"verb","project"}` while the `prq_*` verbs
    log `{"verb","from","to"}`; the plan explicitly requires from/to — 7.4 verbs are pinned to the
    `prq_*` idiom (plus the per-row `supersede` audits in `bvr_activate`).
11. **Disk state verified 2026-09-10**: migrations `0001–0003`; no `ResourceManagement/` in any
    of the four layers; `urls/__init__.py` concatenates 7.1+7.2 only; `templates/projects/` has
    `initiation/` + `planning/` only; tests are `test_initiation_*` only. The four 7.4 literal url
    segments are free today — re-check at Integrate.
