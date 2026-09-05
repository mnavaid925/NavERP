# Frozen build contract — procurement 6.18 Inventory & Warehouse Integration

**Status: FROZEN.** Every name below is the interface. A name that drifts is a silently blank
page region or a `NoReverseMatch` (L7) — the smoke step arbitrates against THIS file, not against
the code. Build plan: `.claude/tasks/todo.md` § `6.18-A`…`6.18-M`. Research:
`.claude/tasks/research-procurement-6.18.md`.

**Phase 4 review scope — path globs, NOT a commit range.** The session-start sha was `56ae21a9`,
but `56ae21a9..HEAD` is **useless as a review range**: four sessions commit to `main` in this one
working tree, so that range interleaves 6.16's `SupplierPerformanceEvaluation/`, 6.17's
`RiskComplianceManagement/` and 6.19's `DocumentKnowledgeManagement/` with ours. Six reviewers
handed it would file findings against other sub-modules, and the `code-fixer` phase would then
"fix" another session's code against a contract it has never read. Scope every reviewer to:

```
apps/procurement/models/InventoryWarehouseIntegration/**
apps/procurement/forms/InventoryWarehouseIntegration/**
apps/procurement/views/InventoryWarehouseIntegration/**
apps/procurement/urls/InventoryWarehouseIntegration/**
templates/procurement/inventorywarehouse/**
```

**Note the `**`** — `templates/procurement/inventorywarehouse/*` is one level too shallow and
would miss every `<entity>/<page>.html` file, i.e. all nine CRUD templates. This sub-module adds
**no flat app-root module** (no `apps/procurement/<something>.py`), so the five globs are complete.

**PRE-FLIGHT, before handing any glob to a reviewer: expand it and count the files.** A glob that
matches nothing makes a reviewer report **clean**, and clean is the answer we are hoping for — so
an under-matching glob is far more dangerous here than an over-matching one, which merely produces
findings we can discard. The same trap applies to the `%s`-anchored shared-file query above: it
returned empty on `navigation.py` simply because nothing had been committed there yet, and empty
is indistinguishable from broken. **Expected counts at Integrate: 4 model files, 4 forms, 7 views,
7 urls, 12 templates.** If an expansion comes back short, the glob is wrong — not the work.

The shared files touched at Integrate (`apps/core/navigation.py`, `admin.py`,
`seed_procurement.py`, the four app-level `__init__.py`, `README.md`) are **not** reviewable by
glob — a glob pulls in three peers' hunks too, and a commit range pulls in their commits. Isolate
our own hunks mechanically instead, since every session tags its sub-module in the commit subject:

```bash
git log --format='%H%x09%s' -- apps/core/navigation.py \
  | grep -E $'\t[a-z]+\\(procurement\\): 6\\.18 ' \
  | cut -f1 \
  | xargs -I{} git show {} -- apps/core/navigation.py
```

Hand the reviewer **that output**, not the file. Same shape for `admin.py`,
`seed_procurement.py`, the four app-level `__init__.py` and `README.md`.

**Anchor on `%s` (the subject), never `--grep`.** `git log --grep` searches the **whole commit
message including the body**, and every coordination commit in this tree names other sessions'
sub-module numbers in its body — so `--grep='6\.18'` returns peer commits and hands a reviewer
exactly the cross-contamination the query exists to prevent. Reproduced: `--grep='6\.16'` returns
`6f607a31`, which is one of **ours**, because its body says "the three sessions building 6.16".
The `%s`-anchored form above requires the `type(scope): 6.18 ` prefix at the **start of the
subject**, which a body mention cannot satisfy.

**Two caveats remain — this is better than eyeballing, not airtight.**
1. `git add <file>` stages the whole file, so if one of our commits swept in a peer's in-flight
   hunk, that hunk appears inside *our* commit and this query hands it to the reviewer as ours.
   Mitigation: commit shared files in the same breath as editing them (a narrow window is what
   keeps this query honest), and scan the output for blocks that aren't ours before handing over.
2. It trusts our own subject-line discipline. A 6.18 commit whose subject omits `6.18` is
   invisible to it.

Scope is **3 entities / 5 model classes + 3 derived no-model pages**. `CountVarianceReview`
[CVR-] is **dropped** this pass (its only consumer is 6.16's scorecard; building a producer
before the consumer ships a table nobody reads).

---

## 0. Concurrency gates — four sessions are live on `apps/procurement`

- **Migration slot is `0028_*`.** Do **NOT** run `makemigrations procurement` until
  `apps/procurement/migrations/0027_*.py` exists on disk. Queue: `0026`=6.16, `0027`=6.17,
  `0028`=**us**, `0029`=6.19. Disk leaf at contract-freeze time: `0025`.
- **Never `seed_procurement --flush`.** Plain idempotent `seed_procurement` only.
- Shared files are **append-only via surgical `Edit`, never `Write`, never from a subagent**:
  the four `apps/procurement/{models,forms,views,urls}/__init__.py`, `apps/procurement/admin.py`,
  `apps/procurement/management/commands/seed_procurement.py` (our dispatch line goes **after
  6.17's**), `apps/core/navigation.py` (**only** the `"6.18"` key), `README.md`.
- `apps/procurement/tests/test_budgetcost_*.py` (4 untracked files) are another session's.
  Never `git add`, never edit.
- **Commits carry NO `Co-Authored-By` trailer** (user preference, confirmed this session).
  One `git add` + one `git commit` per file, PowerShell-safe with `;`.
- **Name checks must run against peers' frozen contracts, not just `apps/`.** In a shared tree,
  absence from disk is NOT absence from a peer's contract: 6.17 and 6.19 both grepped
  `^class ProcurementPolicy` , both correctly found nothing, and both froze a `ProcurementPolicy`
  in `app_label="procurement"` — which raises `RuntimeError: Conflicting 'procurementpolicy'
  models` at startup and breaks `manage.py check` for **every** session sharing this checkout.
  Verified clear for 6.18 against `.claude/tasks/contract-procurement-{6.9,6.13,6.16,6.17,6.19}.md`:
  all five model names (`ReplenishmentPolicy`, `ReplenishmentRun`, `ReplenishmentSuggestion`,
  `MaterialIssue`, `MaterialIssueLine`), all six url segments, and the url names. **Re-run that
  check before adding any name this contract does not already list.**
- **Fourth axis — duplicate url names ALREADY REGISTERED**, whoever's they are. A contract grep
  sees only what peers *intend*; disk sees only what is *written*; **only the resolver sees what
  Django actually registers.** Walk it after `django.setup()`:
  ```python
  from django.urls import get_resolver
  for ns, (prefix, sub) in sorted(get_resolver().namespace_dict.items()):
      names = [n for n in sub.reverse_dict.keys() if isinstance(n, str)]
      # collections.Counter(names) -> any count > 1 is a duplicate
  ```
  **A `grep` for `name="…"` is NOT sufficient and must not be the gate.** `apps/core/urls.py`
  builds its routes with a `crud(slug, name)` factory whose names are **f-strings**
  (`name=f"{name}_detail"`), so grep sees **4** names in that file where the resolver registers
  **49** — 45 routes invisible. Grep also *over*-counts the other way: it reports url modules that
  exist on disk but are not yet wired into `urls/__init__.py` (before Integrate, grep says 401 for
  `procurement` while the resolver says 320, because this sub-module's 27 are not registered yet).
  Grep is a fast pre-check; the resolver walk is the gate.
  Verified clean at contract time: **4,854 namespaced routes across ten namespaces, zero
  duplicates** (`accounting` 177 · `accounts` 20 · `core` 49 · `crm` 304 · `dashboard` 1 · `hrm`
  932 · `inventory` 264 · `procurement` 320 · `scm` 657 · `tenants` 31; `admin` adds 2,099).
  **Re-run at Integrate**, when this sub-module's 27 names become registered — that is the run
  that actually matters. A duplicate url
  *name* is the quietest of all these failures: Django raises nothing, `reverse()` simply resolves
  to whichever pattern registered last, so buttons silently point into another sub-module's page —
  and a smoke test that only asserts status 200 will pass.
- If `manage.py check` starts failing with a conflicting-model error touching policies, it is the
  6.17/6.19 collision above — **not ours**. Do not debug it as ours.

---

## 1. Verified shared-helper contract (read from source, do not assume)

`apps/core/crud.py`:

| helper | context keys it sets |
|---|---|
| `crud_list(request, qs, template, *, search_fields, filters, extra_context, per_page=15)` | `object_list`, `page_obj`, `q` |
| `crud_detail(request, *, model, pk, template, extra_context, select_related)` | `obj` |
| `crud_create(request, *, form_class, template, success_url, extra_context, set_tenant=True, audit=True)` | `form`, `is_edit=False` |
| `crud_edit(request, *, model, pk, form_class, template, success_url, extra_context, audit=True)` | `form`, `obj`, `is_edit=True` |
| `crud_delete(request, *, model, pk, success_url, audit=True)` | — (POST-only, self-defending) |

- `filters` = iterable of `(get_param, orm_lookup, is_int)`. It already hardens junk input
  (`isdecimal` not `isdigit`, over-range refusal, pk=0 refusal, enum membership, `ValueError`
  swallow). **Do not re-implement that hardening.**
- Every form is constructed `form_class(..., tenant=request.tenant)` — **every form in this
  sub-module MUST accept a `tenant=` kwarg.**
- `paginate(request, qs, per_page=15)` returns `page_obj`.

`apps/procurement/views/_common.py` `import *` gives: `messages`, `login_required`,
`get_object_or_404`, `redirect`, `render`, `timezone`, `require_POST`, `crud_create`,
`crud_delete`, `crud_detail`, `crud_edit`, `crud_list`, `tenant_admin_required`,
`write_audit_log`. `paginate` is NOT in it — import it explicitly from `apps.core.crud`.

`apps/procurement/models/_base.py` `import *` gives: `models`, `transaction`, `IntegrityError`,
`F`, `Q`, `Sum`, `timezone`, `Decimal`, `ZERO`, `MAX_Q2`, `q2`, `TenantOwned`, `TenantNumbered`.
`TenantOwned` = `tenant` FK (`related_name="+"`) + `created_at` + `updated_at`.
`TenantNumbered` adds `number = CharField(max_length=20, editable=False)` assigned in `save()`
from `NUMBER_PREFIX` with a 5-try collision retry.

**Imports inside the packages are ABSOLUTE.** Entity modules import sibling models from their
**entity module** (`apps.procurement.models.InventoryWarehouseIntegration.<Entity>`), **never**
from `apps.procurement.models`, until the Integrator wires the re-exports — a package-level
re-export is a star-import cycle at URLconf import time.

---

## 2. File map (24 new files)

```
apps/procurement/models/InventoryWarehouseIntegration/  __init__.py  Policies.py  Runs.py  MaterialIssues.py
apps/procurement/forms/InventoryWarehouseIntegration/   __init__.py  Policies.py  Runs.py  MaterialIssues.py
apps/procurement/views/InventoryWarehouseIntegration/   __init__.py  Policies.py  Runs.py  MaterialIssues.py
                                                        StockPosition.py  ReceiptBinMap.py  CountAccuracy.py
apps/procurement/urls/InventoryWarehouseIntegration/    __init__.py  Policies.py  Runs.py  MaterialIssues.py
                                                        StockPosition.py  ReceiptBinMap.py  CountAccuracy.py
templates/procurement/inventorywarehouse/replenishmentpolicy/{list,detail,form}.html
templates/procurement/inventorywarehouse/replenishmentrun/{list,detail,form}.html
templates/procurement/inventorywarehouse/materialissue/{list,detail,form}.html
templates/procurement/inventorywarehouse/{stock_position,receipt_bin_map,count_accuracy}.html
```

---

## 3. URL names — FROZEN (six literal first segments, zero collisions with the 63 existing)

| route | name |
|---|---|
| `stock-position/` | `stock_position` |
| `replenishment-policies/` | `replenishmentpolicy_list` |
| `replenishment-policies/add/` | `replenishmentpolicy_create` |
| `replenishment-policies/<int:pk>/` | `replenishmentpolicy_detail` |
| `replenishment-policies/<int:pk>/edit/` | `replenishmentpolicy_edit` |
| `replenishment-policies/<int:pk>/delete/` | `replenishmentpolicy_delete` |
| `replenishment-runs/` | `replenishmentrun_list` |
| `replenishment-runs/add/` | `replenishmentrun_create` |
| `replenishment-runs/<int:pk>/` | `replenishmentrun_detail` |
| `replenishment-runs/<int:pk>/edit/` | `replenishmentrun_edit` |
| `replenishment-runs/<int:pk>/delete/` | `replenishmentrun_delete` |
| `replenishment-runs/<int:pk>/generate/` | `replenishmentrun_generate` |
| `replenishment-runs/<int:pk>/release/` | `replenishmentrun_release` |
| `replenishment-runs/<int:pk>/cancel/` | `replenishmentrun_cancel` |
| `replenishment-runs/<int:pk>/lines/<int:line_id>/decide/` | `replenishmentsuggestion_decide` |
| `material-issues/` | `materialissue_list` |
| `material-issues/add/` | `materialissue_create` |
| `material-issues/<int:pk>/` | `materialissue_detail` |
| `material-issues/<int:pk>/edit/` | `materialissue_edit` |
| `material-issues/<int:pk>/delete/` | `materialissue_delete` |
| `material-issues/<int:pk>/submit/` | `materialissue_submit` |
| `material-issues/<int:pk>/post/` | `materialissue_post` |
| `material-issues/<int:pk>/cancel/` | `materialissue_cancel` |
| `material-issues/<int:pk>/lines/add/` | `materialissueline_add` |
| `material-issues/<int:pk>/lines/<int:line_id>/delete/` | `materialissueline_delete` |
| `receipt-bin-map/` | `receipt_bin_map` |
| `count-accuracy/` | `count_accuracy` |

**Literal routes before `<int:pk>` ones — Django is first-match-wins.**

**urls docstring wording — use the ACCURATE form.** The sentence *"this app registers no greedy
`<str:…>` converter anywhere"*, copy-pasted through ~20 existing urls modules, is **FALSE**:
`contract-sign/<str:token>/` exists at `apps/procurement/urls/ContractsManagement/Contracts.py:16`.
Write instead: *no route in this app uses a converter in its **first** path component — every
first segment is a literal — so no module can shadow another's namespace.*

---

## 4. Models — field + CHOICES freeze

### 4.1 `ReplenishmentPolicy` (`Policies.py`, `TenantOwned`, **no NUMBER_PREFIX**)

FKs (all by string, `related_name` prefixed `procurement_replenishment_`):
`item`→`scm.Item` **PROTECT** · `location`→`scm.Location` SET_NULL null/blank (**null = any
location**) · `preferred_vendor`→`core.Party` SET_NULL null/blank ·
`default_org_unit`→`core.OrgUnit` SET_NULL · `default_budget`→`accounting.Budget` SET_NULL ·
`default_gl_account`→`accounting.GLAccount` SET_NULL.

```python
SOURCE_METHOD_CHOICES = [("buy", "Buy"), ("transfer", "Transfer"), ("manufacture", "Manufacture")]   # default "buy"
TRIGGER_MODE_CHOICES  = [("review", "Review then release"), ("auto", "Automatic")]                   # default "review"
```

Fields: `target_level` D(14,2) null/blank · `order_multiple` D(14,2) null/blank ·
`min_order_qty` D(14,2) null/blank · `max_order_qty` D(14,2) null/blank ·
`include_on_order` Bool **default True** · `include_open_requisitions` Bool default True ·
`lead_time_days_override` PositiveInteger null/blank `MaxValueValidator(3650)` ·
`is_active` Bool default True · `notes` Text blank.

Meta: `ordering=["item__sku", "location__code", "id"]`;
`unique_together=("tenant", "item", "location")`;
indexes `prc_rpol_tnt_active_idx` (tenant, is_active, item), `prc_rpol_tnt_item_loc_idx`
(tenant, item, location).

API: `round_quantity(raw)` — the **single** rounding implementation (floor at `min_order_qty`,
round UP to next `order_multiple`, cap at `max_order_qty`, never negative).
`@classmethod resolve(tenant, item, location)` — exact `(item, location)` wins, then
`(item, location=None)` catch-all, else `None`.

`clean()`: cross-tenant rejection on **all six** FKs; `max_order_qty >= min_order_qty` when both
set; `target_level > 0` when set; `preferred_vendor` must hold a supplier/vendor `PartyRole`;
**nullable-unique probe** — `location IS NULL` duplicates are NOT caught by the DB unique (NULLs
compare distinct), so probe explicitly and reject.

**Form `ReplenishmentPolicyForm` excludes:** `tenant`, `created_at`, `updated_at`.

### 4.2 `ReplenishmentRun` [RPL-] + `ReplenishmentSuggestion` (`Runs.py`)

`ReplenishmentRun(TenantNumbered)`, `NUMBER_PREFIX = "RPL"`.
FKs: `location`→`scm.Location` SET_NULL null/blank (**null = whole network**) ·
`generated_by`→`AUTH_USER_MODEL` SET_NULL null/blank **`editable=False`**.

```python
TRIGGER_CHOICES = [("manual", "Manual"), ("scheduled", "Scheduled")]                     # default "manual"
STATUS_CHOICES  = [("draft", "Draft"), ("proposed", "Proposed"),
                   ("released", "Released"), ("cancelled", "Cancelled")]                 # default "draft"
ABC_CHOICES     = [("A", "A"), ("B", "B"), ("C", "C")]     # UPPERCASE
EDITABLE_STATUSES   = ("draft",)
RELEASABLE_STATUSES = ("proposed",)
MAX_SUGGESTIONS     = 500
```

`run_date` Date · `abc_class_filter` Char(1) blank · `notes` Text blank ·
`generated_at`/`released_at` DateTime null/blank **`editable=False`**.

**GOTCHA (put it in `help_text`):** `abc_class_filter` filters **`scm.ReorderRule.abc_class`,
which is UPPERCASE `A/B/C`** — NOT `scm.Location.abc_class`, which is lowercase `a/b/c`.

Meta: `ordering=["-run_date", "-id"]`; `unique_together=("tenant", "number")`;
indexes `prc_rpl_tnt_status_idx` (tenant, status), `prc_rpl_tnt_date_idx` (tenant, run_date).

Verbs: `generate(user)` (atomic + `select_for_update`, deletes this run's existing lines first so
re-generate is idempotent, **9 grouped queries then pure Python**, `bulk_create`, sets
`status="proposed"`), `release(user)` (atomic + `select_for_update`, `proposed` only, groups
`decision="accepted"` by `vendor_id`, one **`scm.PurchaseRequisition` in `draft`** per vendor,
`recalc_totals()`, stamps `suggestion.requisition`, `status="released"`), `cancel(user)`
(`draft`/`proposed` only; refused once released).

Derived properties (never stored): `line_count`, `accepted_count`, `total_value`, `is_editable`,
`status_css`.

`ReplenishmentSuggestion(models.Model)` — child, `related_name="lines"`.
FKs: `run` CASCADE · `item`→`scm.Item` PROTECT · `location`→`scm.Location` PROTECT ·
`reorder_rule`→`scm.ReorderRule` SET_NULL · `policy`→`ReplenishmentPolicy` SET_NULL ·
`vendor`→`core.Party` SET_NULL · `requisition`→`scm.PurchaseRequisition` SET_NULL
**`editable=False`**.

**Every snapshot column `editable=False`**, D(16,4) unless noted: `on_hand_qty`,
`allocated_qty`, `on_order_qty`, `open_requisition_qty`, `available_qty`,
`reorder_point_snapshot`, `target_level_snapshot`, `raw_suggested_qty`, `suggested_qty`,
`unit_cost` D(14,4), `lead_time_days` PositiveInteger.

```python
DECISION_CHOICES = [("pending", "Pending"), ("accepted", "Accepted"),
                    ("snoozed", "Snoozed"), ("dismissed", "Dismissed")]   # default "pending"
```

`snooze_until` Date null/blank · `decision_note` Char(255) blank ·
`line_value` **property** (`suggested_qty × unit_cost`) — derived, never stored.

Meta: `ordering=["item__sku", "id"]`; index `prc_rsg_run_dec_idx` (run, decision).
`clean()`: cross-tenant on `item`/`location`/`vendor`/`policy`/`reorder_rule` against
`run.tenant_id`; `snooze_until` required and future when `decision == "snoozed"`.

**Form `ReplenishmentRunForm` fields:** `location`, `run_date`, `trigger`, `abc_class_filter`,
`notes`. **Excludes:** `tenant`, `number`, `status`, `generated_by`, `generated_at`,
`released_at`, `created_at`, `updated_at`.
**Form `ReplenishmentSuggestionDecisionForm` fields:** `decision`, `snooze_until`, `vendor`,
`decision_note`. **Every snapshot column and `requisition` excluded.**

### 4.3 `MaterialIssue` [MIS-] + `MaterialIssueLine` (`MaterialIssues.py`)

**THE BRIDGE — non-negotiable.** `post()` mints a **draft `scm.StockAdjustment` + lines** and
stores it on `adjustment` (`editable=False`). **`apps/procurement` writes ZERO `scm.StockMove`
rows.** Precedent to cite in the docstring:
`apps/inventory/models/StocktakingCycleCounting/CountPrograms.py:85-125`
(`CountProgram.generate_tasks()` — mint the spine document, stamp provenance, re-read under
`select_for_update()`, reuse rather than double-mint).

**Reason-code mapping (pinned):** `StockAdjustment.reason = "other"` for BOTH directions.
`write_off` would mean destroyed, `found` would mean appeared from nowhere; neither is true of an
internal consumption. **Direction rides the sign of `quantity_delta`.**
`StockAdjustment.clean()` requires notes when reason is `other`, so always stamp:
`f"Via material issue {self.number} ({self.get_movement_type_display()}) · {self.get_purpose_display()}"`.

`MaterialIssue(TenantNumbered)`, `NUMBER_PREFIX = "MIS"`.
FKs: `location`→`scm.Location` **PROTECT** · `org_unit`→`core.OrgUnit` SET_NULL ·
`gl_account`→`accounting.GLAccount` SET_NULL · `requested_by`→`AUTH_USER_MODEL` SET_NULL ·
`issued_by`→`AUTH_USER_MODEL` SET_NULL **`editable=False`** ·
`adjustment`→`scm.StockAdjustment` SET_NULL **`editable=False`** ·
`reservation`→`inventory.InventoryReservation` SET_NULL.

```python
MOVEMENT_TYPE_CHOICES = [("issue", "Issue"), ("return", "Return to stock")]              # default "issue"
PURPOSE_CHOICES = [("cost_centre", "Cost centre"), ("project", "Project"),
                   ("work_order", "Work order"), ("maintenance", "Maintenance"),
                   ("sample", "Sample"), ("other", "Other")]                             # default "cost_centre"
STATUS_CHOICES  = [("draft", "Draft"), ("submitted", "Submitted"),
                   ("posted", "Posted"), ("cancelled", "Cancelled")]                     # default "draft"
EDITABLE_STATUSES    = ("draft",)
POSTABLE_STATUSES    = ("draft", "submitted")
CANCELLABLE_STATUSES = ("draft", "submitted")
```

`reference` Char(64) blank — free text project/job/WO number. **NO FK to `scm.WorkOrder`** (4.8's
manufacturing object; `StockMove` has separate `consumption`/`maintenance` types for a reason).
Say so in `help_text`. `issue_date` Date · `posted_at`/`cancelled_at` DateTime null/blank
**`editable=False`** · `notes` Text blank.

Meta: `ordering=["-issue_date", "-id"]`; `unique_together=("tenant", "number")`; indexes
`prc_mis_tnt_status_idx`, `prc_mis_tnt_date_idx`, `prc_mis_tnt_mvt_idx`.

API: `total_value` (one aggregate `Σ quantity × unit_cost`), `on_hand_at_location(item_ids)`
(**LOCAL** mirror of `apps/scm/views/_helpers.py:157`'s shape — ONE grouped
`Sum(StockMove.quantity)` over `(tenant, location, item_id__in)`; **do NOT import
`apps.scm.views._helpers`**), `post(user)`, `submit(user)`, `cancel(user)`.

`post(user)`: atomic + `select_for_update` on header; refuse unless status in
`POSTABLE_STATUSES`; refuse when no lines; **availability guard for `movement_type == "issue"`
only** (one grouped query, per-item `ValidationError` on shortfall); **reuse `self.adjustment_id`
if already set**; mint adjustment + lines; stamp `adjustment`, `status="posted"`, `posted_at`,
`issued_by`; `write_audit_log(user, self, "post", {"adjustment": adj.number})`.

**Cancellation after posting is REFUSED** — correct with the mirror document (a `return` against
the same location), never by deleting.

`clean()`: cross-tenant on all seven FKs; `purpose == "other"` requires `notes`; a
`movement_type == "return"` with `reservation` set is rejected (a reservation is consumed by an
issue, not a return); `reservation.item`/`location` consistent with header location when set.

Badge maps, **colour-named only**: `STATUS_CSS` draft→muted, submitted→amber, posted→green,
cancelled→slate; `MOVEMENT_CSS` issue→info, return→green.

**Form `MaterialIssueForm` fields:** `location`, `movement_type`, `purpose`, `reference`,
`issue_date`, `org_unit`, `gl_account`, `requested_by`, `reservation`, `notes`.
**Excludes:** `tenant`, `number`, `status`, `adjustment`, `issued_by`, `posted_at`,
`cancelled_at`, `created_at`, `updated_at`.

`MaterialIssueLine(models.Model)` — child, `related_name="lines"`.
FKs: `issue` CASCADE · `item`→`scm.Item` PROTECT · `lot_serial`→`scm.LotSerial` SET_NULL ·
`gl_account`→`accounting.GLAccount` SET_NULL.
`quantity` D(16,4) `MinValueValidator(Decimal("0.0001"))` ·
`unit_cost` D(14,4) default 0 **`editable=False`** (snapshot of `Item.average_cost`, stamped in
`save()` when unset) · `notes` Char(255) blank · `line_value` **property**.
Meta: `ordering=["item__sku", "id"]`.
**Form `MaterialIssueLineForm` fields:** `item`, `lot_serial`, `quantity`, `gl_account`, `notes`
— **`unit_cost` excluded** (snapshot, not an input).

---

## 5. View context keys — FROZEN (L7: an unpinned name is a blank region)

Every view `@login_required`; every mutating verb `@require_POST`; every queryset
`filter(tenant=request.tenant)` — **never `.all()`**.

### `replenishmentpolicy_list` (`crud_list`)

base `object_list`, `page_obj`, `q` **+** `stats` (`total`, `active`, `inactive`, `auto` — ONE
conditional aggregate), `items`, `locations`, `vendors`, `source_choices`, `trigger_choices`.
search: `item__sku`, `item__name`, `location__code`, `location__name`, `preferred_vendor__name`,
`notes`. filters: `("item","item_id",True)`, `("location","location_id",True)`,
`("vendor","preferred_vendor_id",True)`, `("source_method","source_method",False)`,
`("trigger_mode","trigger_mode",False)`, `("is_active","is_active",False)`.

### `replenishmentpolicy_detail` (`crud_detail`)

base `obj` **+** `rule` (matching `scm.ReorderRule` or `None`), `effective` (dict with
`reorder_point`, `safety_stock`, `target_level`, `lead_time_days`, each carrying a `source` of
`"policy override"` / `"reorder rule"`), `recent_suggestions` (last 10), `rule_url`.

### `replenishmentpolicy_create` / `_edit` / `_delete`

`form`, `is_edit` (+ `obj` on edit). `_delete` POST-only.

### `replenishmentrun_list` (`crud_list`)

base **+** `stats` (`total`, `draft`, `proposed`, `released`), `locations`, `status_choices`,
`trigger_choices`, `abc_choices`.
search: `number`, `notes`, `location__code`, `location__name`.
filters: `("status","status",False)`, `("trigger","trigger",False)`,
`("location","location_id",True)`, `("abc","abc_class_filter",False)`.

### `replenishmentrun_detail` (`crud_detail`)

base `obj` **+** `lines` (paginated 25 via `paginate`,
`select_related("item","item__uom","location","vendor","policy","requisition")`),
`line_page_obj`, `decision_choices`, `vendors`, `totals` (`line_count`, `accepted`, `snoozed`,
`dismissed`, `pending`, `accepted_value`), `can_generate`, `can_release`, `can_cancel`,
`requisitions` (distinct released PRs, urls reversed **in Python**), `truncated`,
`sku_match_note`.

### `replenishmentrun_generate` / `_release` / `_cancel`

POST-only. `_release` additionally **`@tenant_admin_required`** (it raises requisitions that
commit money). `ValidationError` → `messages.error` → redirect to detail.

### `replenishmentsuggestion_decide`

POST-only. Line loaded `get_object_or_404(ReplenishmentSuggestion, pk=line_id, run__pk=pk,
run__tenant=request.tenant)` — **tenant reached through the run; this IS the IDOR boundary.**

### `materialissue_list` (`crud_list`)

base **+** `stats` (`total`, `draft`, `submitted`, `posted`, `issues`, `returns`), `locations`,
`org_units`, `status_choices`, `movement_choices`, `purpose_choices`.
search: `number`, `reference`, `notes`, `location__code`, `location__name`, `org_unit__name`.
filters: `("status","status",False)`, `("movement_type","movement_type",False)`,
`("purpose","purpose",False)`, `("location","location_id",True)`,
`("org_unit","org_unit_id",True)`.

### `materialissue_detail` (`crud_detail`)

base `obj` **+** `lines` (`select_related("item","item__uom","lot_serial","gl_account")`),
`line_form`, `total_value`, `adjustment`, `adjustment_url`, `availability` (dict
`{item_id: on_hand}` from the ONE grouped query, so each line shows a shortfall flag **before**
posting), `can_submit`, `can_post`, `can_cancel`, `can_edit`, `boundary_note`, `ledger_note`.

- `boundary_note` — verbatim intent: *return to **stock** is this document; return to **vendor**
  is 6.12 `ReturnToVendor` [RMA-]*, with a link, so nobody files one as the other.
- `ledger_note` — verbatim intent: *posting mints a **DRAFT** stock adjustment; stock moves only
  when SCM posts it*, with a link to `scm:stockadjustment_detail`.

### `materialissue_submit` / `_post` / `_cancel`

POST-only. `_post` additionally **`@tenant_admin_required`**. Shortfall `ValidationError`
surfaces per item.

### `materialissueline_add` / `_delete`

POST-only, header must be draft. Line loaded `pk=line_id, issue__pk=pk,
issue__tenant=request.tenant`.

### `stock_position` (derived, no model)

**Context:** `page_obj`, `object_list`, `q`, `items`, `locations`, `vendors`, `view_choices`,
`selected_view`, `stats` (`rows`, `below_point`, `shortage`, `no_cover`), `row_cap`, `truncated`,
`sku_match_note`.
**Row dict keys:** `item`, `location`, `on_hand`, `allocated`, `held`, `available`, `on_order`,
`expected_date`, `expected_vendor`, `expected_po_number`, `expected_po_url`,
`open_requisition_qty`, `reorder_point`, `avg_daily_demand`, `days_of_cover`, `below_point`,
`policy_vendor`, `raise_requisition_url`.
`view` ∈ `all` | `below_point` | `shortage` | `no_cover`. `ROW_CAP = 500`.
Availability formula is **reused verbatim** from
`apps/inventory/views/InventoryTrackingControl/StockLevels.py:124` —
`available = on_hand − (SO allocations + reservations) − non-sellable`.
**Do not invent a second definition.**

### `receipt_bin_map` (derived, no model)

**Context:** `page_obj`, `object_list`, `q`, `locations`, `status_choices`, `selected_location`,
`selected_status`, `date_from`, `date_to`, `stats` (`receipts`, `fully_putaway`,
`partially_putaway`, `in_staging`), `row_cap`, `truncated`, `reference_note`, `links`.
**Row dict keys:** `grn`, `grn_url`, `staging_location`, `received_qty`, `bins` (list of
`{location, path, quantity, capacity, fullness_pct, capacity_css}`), `putaway_tasks` (list of
`{task, url, status, status_css, to_location}`), `unputaway_qty`, `is_unputaway`, `putaway_css`.
**The receipt→bin link IS `StockMove.reference == grn.number`** (posted at
`apps/scm/views/_helpers.py:328-330`, indexed `StockMoves.py:60`). A bin **IS**
`scm.Location(location_type="bin")` — **no Bin/Zone model.** Paginate the GRNs FIRST, then five
grouped queries regardless of page size.

### `count_accuracy` (derived, no model)

**Context:** `stats` (`tasks_total`, `tasks_scheduled`, `tasks_counted`, `tasks_reconciled`,
`tasks_cancelled`, `lines_counted`, `lines_with_variance`, `variance_rate_pct`,
`net_variance_qty`, `abs_variance_qty`, `variance_value`, `accuracy_pct`), `item_rows`,
`location_rows`, `program_rows`, `locations`, `window_choices`, `selected_window`,
`selected_location`, `date_from`, `date_to`, `row_cap`, `truncated`, `attribution_note`, `links`.
**`item_rows`:** `item`, `count_lines`, `variance_lines`, `net_variance`, `abs_variance`,
`variance_value`, `accuracy_pct`, `repeat_offender`.
**`location_rows`:** `location`, `path`, `count_lines`, `variance_lines`, `net_variance`,
`accuracy_pct`, `accuracy_css`.
**`program_rows`:** `program`, `cadence_label`, `last_run_date`, `is_due`, `location`,
`abc_class`, `url`.
**`CycleCountTaskLine.variance` is a Python property and CANNOT be aggregated** — roll up as
`Sum(counted) − Sum(expected)` in the annotation. State that in a comment.
`attribution_note` says plainly that root-cause attribution is **not recorded yet** and that
feeding count variance into a supplier scorecard belongs to **6.16**. The page must not imply a
capability it lacks.

---

## 6. Rules that apply everywhere

1. **Zero `scm.StockMove` writes from `apps/procurement`.** The smoke step asserts the row count
   is unchanged across a `post()`.
2. **No new Bin/Zone/Item/Location/StockMove/ReorderRule model.** FK by string into `scm.*`,
   `inventory.*`, `core.*`, `accounting.*` (L36).
3. **Every derived quantity is a grouped aggregate.** Never a per-row aggregate inside a loop.
   The `_on_order_map` shape is **two queries, not one** — a single annotation fans out and
   multiplies `ordered` by the receipt count.
4. **Peer apps do not import each other's internals.** Mirror `_insufficient_stock()` and
   `_on_order_map()` shapes locally; do not import `apps.scm.views._helpers`.
5. **Every url is `reverse()`d in Python, never in a template**, for dict-row pages.
6. `request.tenant is None` renders an **empty page, never a 500**. Junk GET params narrow
   nothing and return 200.
7. **theme.css badges are colour-named ONLY** — `badge-green/red/amber/info/muted/slate`.
   `-success/-warning/-danger` do **not** exist and render unstyled (L33). stat-icon colours:
   `blue/green/orange/purple/slate` only.
8. `TenantUniqueMixin` comes **FIRST** in every form's MRO so `instance.tenant` is stamped before
   `full_clean()` — otherwise every CREATE is falsely rejected as cross-tenant.
9. A narrowed `<select>` is UX, **not** an authorization boundary — the `clean()`
   `_reject_foreign` re-check is the boundary. Say so in each form's docstring.
10. Multi-line template notes use `{% comment %}`, never `{# #}` (single-line only, leaks).
11. Test subslug is **`invwarehouse`**: every test function `test_invwarehouse_*`, every
    module-level helper `_invwarehouse_*`.
12. The seeder **never calls `post()`** — it creates draft/submitted/return documents only, so a
    seed run writes no `scm.StockAdjustment` and never couples us to `seed_scm --flush`.
    Posting is exercised by the throwaway `temp/` smoke script instead.

---

## 7. `LIVE_LINKS["6.18"]` — one entry per NavERP.md bullet, no plumbing

```python
"6.18": {
    "Stock Level Visibility":       "procurement:stock_position",
    "Reorder Point Automation":     "procurement:replenishmentrun_list",
    "Goods Issue/Return to Stock":  "procurement:materialissue_list",
    "Warehouse Location Mapping":   "procurement:receipt_bin_map",
    "Cycle Count Integration":      "procurement:count_accuracy",
},
```

`ReplenishmentPolicy` gets **no** sidebar key — it is configuration behind an analysis page,
reached from the run list (the `ReceiptTolerancePolicy` / `SpendClassificationRule` /
`ReorderRule` precedent documented at `navigation.py:1633-1648`).
