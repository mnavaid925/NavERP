# Test contract — Procurement 6.19 Document & Knowledge Management

**Phase 6 step 1 output.** Every name below was read out of the code **as it stands now** (30 fix
commits after `contract-procurement-6.19.md` was frozen) and, where marked ✅, **executed** against
the real test database. `contract-procurement-6.19.md` is the BUILD contract and is stale in
[§11](#11-where-the-code-disagrees-with-the-stale-build-contract) — this file wins.

Fixtures landed in `apps/procurement/tests/conftest.py` (appended, lines ~2126-2700).

---

## 1. Scope, files, naming (L47 — non-negotiable)

| File | Owns |
|---|---|
| `apps/procurement/tests/test_dk_models.py` | model defaults, `__str__`, CHOICES, auto-numbers, properties, `clean()`, `unique_together`, the reminder engine, the extraction helpers |
| `apps/procurement/tests/test_dk_forms.py` | the four forms: `Meta.fields`, required, **excluded** system fields, queryset narrowing, `_reject_foreign`, `clean_file` |
| `apps/procurement/tests/test_dk_views.py` | 33 routes: status, template, **context keys**, filters, pagination, the verbs' happy paths, `django_assert_max_num_queries` |
| `apps/procurement/tests/test_dk_security.py` | tenancy/IDOR, classification (I5), authz ladder, CSRF, `require_POST`, junk params, crafted FKs |

* Every test function `test_dk_*`. Every module-level helper `_dk_*`.
* `conftest.py` is **owned by step 1** — do not edit it from a later step. If you truly need one
  more row, build it in the test module from the `_dk_*` helpers (they are importable:
  `from apps.procurement.tests.conftest import _dk_document, _dk_revision, _dk_approve,
  _dk_policy, _dk_resource, _dk_party, _dk_documents`).
* Run: `venv\Scripts\python.exe -m pytest -q apps/procurement/tests/test_dk_<lane>.py`
  (`--nomigrations` is fine while iterating; never in `pytest.ini`, never for a final claim).
* Determinism: `timezone.localdate()` / `timezone.now()`, **never** `datetime.date.today()` (L16).

---

## 2. Imports that resolve (verified)

```python
from apps.procurement.models import (              # package root re-exports — all four
    ProcurementDocument, ProcurementDocumentRevision, ProcurementPolicy, KnowledgeResource,
    ProcurementAlert, PolicyAttestation,           # 6.1 alert inbox / 6.17 attestation ledger
    expiring_documents, run_document_reminders, run_document_reminders_audited)
from apps.procurement.forms import (
    ProcurementDocumentForm, ProcurementDocumentRevisionUploadForm,
    ProcurementPolicyForm, KnowledgeResourceForm)
```

The `*_CHOICES` tuples and module constants are **deliberately NOT hoisted** into
`apps/procurement/models/__init__.py` (the 6.14/6.15 rule). Reach them either through the class
(`ProcurementDocument.DOC_TYPE_CHOICES`, `.STATUS_CSS`, `.EXPIRY_WARN_DAYS`, …) or through the
entity module:

```python
from apps.procurement.models.DocumentKnowledgeManagement.Documents import (
    CLASSIFICATION_CHOICES, DOC_TYPE_CHOICES, EXPIRY_FILTER_CHOICES, EXPIRY_WARN_DAYS,
    REINDEX_ROW_CAP, REMINDER_WINDOW_DAYS, STATUS_CHOICES, normalize_tags)
from apps.procurement.models.DocumentKnowledgeManagement.Revisions import (
    EXTRACT_MAX_CHARS, MAX_EXTRACT_PAGES, NOTE_BAD_FILE, NOTE_NO_EXTRACTOR, NOTE_NO_TEXT_LAYER,
    NOTE_UNREADABLE_PATH, PLAIN_TEXT_EXTENSIONS, extract_document_text, file_sha256,
    next_revision_no)
from apps.procurement.models.DocumentKnowledgeManagement.Policies import (
    ADVISORY_NOTE, MAX_CHAIN_DEPTH, POLICY_TYPE_CHOICES, THRESHOLD_BASIS_CHOICES,
    supersession_conflict)
from apps.procurement.models.DocumentKnowledgeManagement.KnowledgeResources import (
    AUDIENCE_CHOICES, CATEGORY_CHOICES, FEATURED_CAP, LIBRARY_NOTE, RESOURCE_TYPE_CHOICES)
from apps.procurement.views.DocumentKnowledgeManagement.Documents import (
    FILE_TEXT_SEARCH_MIN_CHARS, REINDEX_TIME_BUDGET_SECONDS, SEARCH_NOTE, DETAIL_FAN_OUT_CAP)
from apps.procurement.views.DocumentKnowledgeManagement.Revisions import (
    APPROVAL_CHOICES, DOCUMENT_FACET_CAP, REVISION_NOTE, UPLOAD_NOTE)
from apps.procurement.views.DocumentKnowledgeManagement.Policies import (
    REVIEW_CHOICES, SUPERSEDED_BY_CAP)
from apps.procurement.views.DocumentKnowledgeManagement.KnowledgeResources import (
    FEATURED_CHOICES, USAGE_COUNT_CEILING)
from apps.procurement.views._helpers import CLASSIFICATION_NOTE, OPEN_CLASSIFICATIONS, \
    holder_name, readable_document_q
from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES  # 13 exts, 20 MB
```

---

## 3. Fixtures (in `apps/procurement/tests/conftest.py`)

Root conftest already provides `tenant_a`, `tenant_b`, `admin_user` (tenant A, `is_tenant_admin`),
**`member_user` (tenant A, NOT an admin)**, `admin_b`, `client_a`, `client_b`, **`member_client`**.
No `dk_member_a` was added — `member_user` / `member_client` are the non-admin pair. The app
conftest also already has `usd` (Currency), `org_unit_a` / `org_unit_b` (core.OrgUnit).

### 3.1 Infrastructure

| Fixture | What it is |
|---|---|
| `dk_media_root(settings, tmp_path)` | Points `settings.MEDIA_ROOT` at `tmp_path/media`. **Request it (directly or transitively) in any test that stores a file** — otherwise the bytes land in the real `media/`. `FileSystemStorage` drops its cached `location` on `setting_changed`, so this really moves the write. ✅ asserted: `revision.file.path.startswith(dk_media_root)` |
| `dk_supplier_a` / `dk_supplier_b` | `core.Party` + `PartyRole(role="supplier", status="active")` — the `?supplier=` facet and `_supplier_parties()` both require the role |

### 3.2 Documents (tenant A unless noted)

| Fixture | State |
|---|---|
| `dk_document_draft_a` | `draft` / `internal`, owner+creator `admin_user`, **0 revisions**, pointer 0 → the one document `pdocument_delete` really deletes |
| `dk_document_active_a` | `active` / `internal`, `supplier=dk_supplier_a`, `effective_date`= -30d, `review_on`= +180d |
| `dk_document_superseded_a` | `superseded` / `internal` |
| `dk_document_archived_a` | `archived` → checkout and revision upload are both refused |
| `dk_document_public_a` | `public`, **no owner**, `extracted_text` contains `harborcoverage` |
| `dk_document_confidential_a` | `confidential`, owner+creator `admin_user`, `extracted_text` contains `zephyrindemnity` |
| `dk_document_restricted_a` | `restricted`, owner+creator `admin_user`, `extracted_text` contains `quillbaseline` |
| `dk_document_confidential_member_a` | `confidential` **owned by `member_user`** — the positive half of the read rule |
| `dk_document_expiring_a` | `expires_on = today + 7` (inside `EXPIRY_WARN_DAYS = 30`) |
| `dk_document_expired_a` | `expires_on = today - 3` |
| `dk_document_review_due_a` | `review_on = today - 1` |
| `dk_document_over_retention_a` | `retention_until = today - 1` |
| `dk_document_locked_a` | `checked_out_by = member_user`, `checked_out_at = now()` |
| `dk_document_chain_a` | **draft → active via a real approval**: r1 approved (pointer = 1) + r2 pending; both revisions carry a real `.txt` whose text was really extracted |
| `dk_documents_page2_a` | list of 16 `public`/`active` rows → forces page 2 at `per_page = 15` |
| `dk_document_b` | **tenant B** — the IDOR / crafted-FK target |

### 3.3 Revisions

| Fixture | State |
|---|---|
| `dk_revision_approved_a` | r1 of `dk_document_chain_a` — `is_approved=True`, `is_current=True`, `sha256` 64 chars, text contains `soleplate`, `extraction_note == ""` |
| `dk_revision_pending_a` | r2 of the same document — pending, not current |
| `dk_revision_confidential_a` | approved r1 of `dk_document_confidential_a` |
| `dk_revision_no_file_a` | r1 of `dk_document_superseded_a` with `file == ""` — the download guard |
| `dk_revision_b` | approved r1 of `dk_document_b` (tenant B) |

### 3.4 Policies

| Fixture | State |
|---|---|
| `dk_policy_v1_archived_a` | "Competitive Bidding Threshold" **v1.0 archived**, `published_at` set |
| `dk_policy_published_a` | same title **v2.0 published**, `previous_version = v1.0`, threshold `25000.00` / `per_purchase_order` / `usd`, `applies_to=org_unit_a`, `document=dk_document_active_a`, `requires_acknowledgment=True`, `next_review_on = +180d` |
| `dk_policy_draft_a` | same title **v3.0 draft**, `previous_version = v2.0` → publishing it must archive v2.0 |
| `dk_policy_review_due_a` | "Supplier Code of Conduct" v1.0 published, `next_review_on = today - 1` |
| `dk_attestation_a` | one 6.17 `PolicyAttestation` on `dk_policy_published_a` (status `pending`) → `ppolicy_delete` refuses |
| `dk_policy_b` | **tenant B** |

### 3.5 Knowledge resources

| Fixture | State |
|---|---|
| `dk_resource_featured_a` | `published` + `is_featured`, `rfp_template`/`it_software`/`buyer`, `document=dk_document_active_a` |
| `dk_resource_published_a` | `published`, not featured, `checklist`/`facilities`/`all` |
| `dk_resource_draft_a` | `draft` |
| `dk_resource_archived_a` | `archived` |
| `dk_resource_used_a` | `published`, `usage_count = 7`, `last_used_at` = -2d |
| `dk_resource_review_due_a` | `published`, `review_on = today - 1` |
| `dk_resource_b` | **tenant B** |

### 3.6 Three traps in the fixtures

1. **`objects.create()` does not call `clean()`.** Fixture `tags` are stored verbatim (already
   normalised). Assert `normalize_tags` / `clean()` through the model or the form, never by
   reading a fixture back.
2. **`_dk_revision` runs the REAL `extract_document_text`**, and `_dk_approve` performs exactly
   the writes `pdocrevision_approve` performs. The fixture state IS the production state — you do
   not need to hand-build a pointer.
3. `dk_policy_published_a` transitively pulls in `dk_policy_v1_archived_a`, `dk_document_active_a`,
   `dk_supplier_a`, `org_unit_a` and `usd`. Register-count assertions must account for the
   document that comes with it.

---

## 4. Models

### 4.1 `ProcurementDocument` — `NUMBER_PREFIX = "PDOC"`, base `TenantNumbered`

Fields (verified against `_meta`): `tenant`, `created_at`, `updated_at`, `number`(editable=False),
`title`, `doc_type`(default `"other"`), `description`, `tags`, `classification`(default
`"internal"`), `status`(default `"draft"`), `owner`, `supplier_visible`(False), `effective_date`,
`expires_on`, **`review_on`**, `retention_until`, `current_revision_no`(0, editable=False),
`checked_out_by`/`checked_out_at`(editable=False), `extracted_text`(editable=False),
**`supplier`** (`core.Party` — *not* `vendor`), `contract`(`scm.SupplierContract`),
`purchase_order`(`scm.PurchaseOrder`), `sourcing_event`(`procurement.SourcingEvent`),
`created_by`(editable=False).

Reverse accessors: `revisions`, `policies`, `knowledge_resources`.

```
DOC_TYPE_CHOICES        quote specification warranty certificate insurance sow drawing
                        correspondence policy template other                       (11)
CLASSIFICATION_CHOICES  public internal confidential restricted                     (4)
STATUS_CHOICES          draft active superseded archived                            (4)
EXPIRY_FILTER_CHOICES   expiring expired review_due over_retention   (a FACET, not a column)
EXPIRY_WARN_DAYS = 30   REMINDER_WINDOW_DAYS = 30   REINDEX_ROW_CAP = 25
STATUS_CSS          draft badge-muted / active badge-green / superseded badge-amber /
                    archived badge-slate
CLASSIFICATION_CSS  public badge-info / internal badge-slate / confidential badge-amber /
                    restricted badge-red
```

* `Meta.ordering = ["-created_at", "-id"]`, `unique_together = ("tenant", "number")`, five indexes
  (`prc_pdoc_tnt_status_idx`, `_type_`, `_expiry_`, **`prc_pdoc_tnt_review_idx`** (added by I16),
  `_sup_`), `verbose_name = "Procurement Document"`.
* `__str__` → `f"{self.number or 'PDOC'} · {self.title}"` (middle dot U+00B7). On an **unsaved**
  instance it must read `"PDOC · …"`, never `" · …"`.
* Properties: `tag_list`, `status_css`, `classification_css` (both fall back to `badge-slate`),
  `is_expired`, `is_expiring`, `is_review_due`, `is_over_retention`, `is_checked_out`,
  **`current_revision`**.
* **`current_revision` filters `is_approved=True`** (I1). ✅ With the pointer forced to an
  unapproved r2 it returns `None`. Note: `revision.is_current` is number-equality only and returns
  `True` in that same artificial state — that is deliberate (it drives `{% if not r.is_current %}`
  on the delete button, the conservative direction) and all three templates guard the green
  "Current" badge with `is_current AND is_approved`. **Do not assert `is_current is False` there.**
* `clean()`: normalises `tags` in place; rejects a cross-tenant `supplier` / `contract` /
  `purchase_order` / `sourcing_event` with `"That record belongs to another workspace."`; rejects
  `expires_on < effective_date` on key `expires_on` with `"The expiry date cannot be before the
  effective date."`
* `normalize_tags("Warranty, HVAC ,warranty") == "warranty, hvac"` (lower, strip, dedupe,
  first-seen order, `", "`-joined).

### 4.2 `ProcurementDocumentRevision` — child, **no** number prefix, base `TenantOwned`

`document`(CASCADE, related_name `revisions`), `revision_no`(1, editable=False), `file`
(`upload_to="procurement/documents/%Y/%m/"`), `original_filename`/`file_size`/`sha256`
(editable=False), **`change_note` — the only user-typed column**, `is_approved`(False)/
`approved_by`/`approved_at`(editable=False), `uploaded_by`(editable=False), `extracted_text` and
**`extraction_note`** (editable=False — *not* `extract_note`).

* **There is no `uploaded_at`.** `created_at` IS the upload moment.
* `Meta.ordering = ["-revision_no", "-id"]`, `unique_together = ("tenant", "document",
  "revision_no")`, **one** index `prc_pdrev_tnt_appr_idx` (`prc_pdrev_tnt_doc_idx` was dropped —
  M20).
* `__str__` → `f"{document.number} r{revision_no}"`; on an instance with **no** `document_id` it
  reads `"PDOC r<n>"` and must not raise.
* `is_current` → `revision_no == document.current_revision_no` (False when `document_id` is None).
* `clean()`: looks the parent's `tenant_id` up **by VALUES query on `document_id`** and errors on
  key `document`.
* Helpers: `next_revision_no(document)` → `Max(revision_no) + 1` or 1;
  `file_sha256(upload)` → hex digest, `seek(0)` before **and** after, `""` for `None`;
  `extract_document_text(revision)` → `(text, note)`, **never raises**:

| condition | returns |
|---|---|
| no `file` / no `path` | `("", NOTE_UNREADABLE_PATH)` |
| `.txt` / `.csv` with text | `(text[:EXTRACT_MAX_CHARS], "")` |
| `.txt` / `.csv` blank | `("", NOTE_NO_TEXT_LAYER)` |
| unreadable open | `("", NOTE_BAD_FILE)` |
| `.pdf`, pdfplumber missing | `("", NOTE_NO_EXTRACTOR)` |
| `.pdf` malformed | `("", NOTE_BAD_FILE)` |
| any other extension | `("", NOTE_NO_TEXT_LAYER)` |

  `EXTRACT_MAX_CHARS = 200_000`, `PLAIN_TEXT_EXTENSIONS = {".txt", ".csv"}`,
  `MAX_EXTRACT_PAGES = 500`.

### 4.3 `ProcurementPolicy` — `NUMBER_PREFIX = "PPOL"`

`title`, `policy_type`(default `purchasing_rule`), `summary`(CharField 500), `body`,
`version_number`(default `"1.0"`), `previous_version`(self FK, SET_NULL, reverse `superseded_by`),
`status`(default `draft`), `effective_from`, `published_at`(editable=False),
**`next_review_on`** (← the policy's review column; documents and resources use `review_on`),
`threshold_amount`(Decimal 14,2, `MinValueValidator(0)`), `threshold_basis`(default `""`),
`threshold_currency`(`accounting.Currency` — **global table, no tenant**),
`requires_acknowledgment`(False), `applies_to`(`core.OrgUnit`), `owner`,
`document`(`ProcurementDocument`, reverse `policies`), `created_by`.
Reverse: `superseded_by`, **`attestations`** (6.17 `PolicyAttestation`, CASCADE).

```
POLICY_TYPE_CHOICES     purchasing_rule approval_limit competitive_bidding sole_source
                        supplier_code_of_conduct ethics_conflict sustainability
                        data_security other                                        (9)
STATUS_CHOICES          draft published archived                                    (3)
THRESHOLD_BASIS_CHOICES per_line per_requisition per_purchase_order per_contract_year
                        annual_supplier_spend                                       (5)
STATUS_CSS  draft badge-muted / published badge-green / archived badge-slate
MAX_CHAIN_DEPTH = 50
```

* `unique_together = (("tenant","number"), ("tenant","title","version_number"))` — three indexes
  incl. `prc_ppol_tnt_review_idx`.
* `__str__` → `f"{self.title} v{self.version_number}"` (**title**, not number).
* `threshold_label` → `"USD 25,000.00 per purchase order"`; `""` when `threshold_amount is None`.
  ✅ `dk_policy_published_a.threshold_label.startswith("USD 25,000.00")`.
* `is_review_due` → `next_review_on <= localdate()`.
* `clean()`: cross-tenant backstop on `applies_to` / `document` / `previous_version` (**not**
  `threshold_currency` — global table); `supersession_conflict()` for self-supersession and every
  longer loop; amount-without-basis errors on `threshold_basis`, basis-without-amount errors on
  `threshold_amount`.
* `supersession_conflict(policy, candidate)` → `None` when fine, else the sentence. Self → *"A
  policy cannot supersede itself…"*; a chain back to `policy` → *"…would make the version chain
  loop…"*; a pre-existing loop → *"…already loops…"*; past `MAX_CHAIN_DEPTH` → *"…longer than 50
  versions…"*.

### 4.4 `KnowledgeResource` — `NUMBER_PREFIX = "PKR"`

`title`, `resource_type`(default `guide`), `category`(default `general`), `audience`(default
`all`), `summary`(500), `body`, `tags`, `status`(default `draft`), `is_featured`(False),
`usage_count`(0, editable=False), `last_used_at`(editable=False), **`review_on`**, `owner`,
`document`(reverse `knowledge_resources`), `created_by`.

```
RESOURCE_TYPE_CHOICES  rfp_template rfq_template evaluation_scorecard negotiation_playbook
                       checklist guide sample_document training                     (8)
CATEGORY_CHOICES       general it_software facilities logistics professional_services
                       raw_materials capex marketing other                          (9)
AUDIENCE_CHOICES       all requester buyer approver legal                           (5)
STATUS_CHOICES         draft published archived                                     (3)
FEATURED_CAP = 6
```

* `Meta.ordering = ["-is_featured", "-created_at", "-id"]` — featured first, id tiebreak (stable
  paging), `unique_together = ("tenant","number")`, three indexes.
* `__str__` → `f"{self.number or 'PKR'} · {self.title}"`.
* `tag_list`, `status_css`, `is_review_due` (`review_on <= localdate()`).
  **`has_been_used` was DELETED (M16)** — do not test for it.
* `clean()`: normalises `tags`; cross-tenant backstop on `document` only.

### 4.5 Reminder engine (module-level in `Documents.py`, **not** a model)

```python
expiring_documents(tenant, *, on=None)  # [{"document", "days_left", "reason"}] soonest first
run_document_reminders(tenant, user)    # {"raised": n, "skipped_open": n}
run_document_reminders_audited(tenant, user)   # @transaction.atomic; + one audit row
```
* Scans **only** `status__in=("draft","active")`, `expires_on` **or** `review_on <= today + 30`.
  Expiry outranks review on the same row; `reason` is `"expires"` / `"review"`;
  `days_left` goes negative once past.
* Alert written: `kind="deadline"`, `status="open"`,
  `severity = "critical" if days_left <= 7 else "warning"`,
  `link_url = f"/procurement/documents/{pk}/"`, `due_at=None`.
* Dedupe is against `ProcurementAlert.OPEN_STATUSES == ("open", "acknowledged")` on `link_url`.
* ✅ **Measured**: first press `{"raised": 3, "skipped_open": 0}`; second press
  `{"raised": 0, "skipped_open": 3}` in **exactly 2 queries** (`django_assert_max_num_queries(2)`
  around a DIRECT call to `run_document_reminders` — through the VIEW the request costs ~11 with
  session/user/tenant/audit, so measure the function, not the POST).

---

## 5. Forms — `Meta.fields` and what is NOT a field

### `ProcurementDocumentForm(TenantUniqueMixin, TenantModelForm)` — 15 fields
```
title doc_type description tags classification owner supplier_visible
effective_date expires_on review_on retention_until
supplier contract purchase_order sourcing_event
```
Required: **`title`, `doc_type`, `classification`** only.
**NOT fields (assert absent):** `tenant`, `number`, `status`, `current_revision_no`,
`checked_out_by`, `checked_out_at`, `extracted_text`, `created_by`, `created_at`, `updated_at`,
and **no `file`** (bytes only ever arrive through the revision upload form).
`__init__(tenant=None)` → every one of `owner`/`supplier`/`contract`/`purchase_order`/
`sourcing_event` becomes `.none()`. With a tenant: `owner` = active users of the tenant ordered by
`username`; `supplier` = tenant Parties with `roles__role__in=("supplier","vendor")` `.distinct()`
by name; the other three are tenant-scoped by `TenantModelForm` and re-ordered `-id`;
all five get `empty_label = "- none -"`.
`clean()` calls `_reject_foreign(..., ["supplier","contract","purchase_order","sourcing_event"])` →
field error `"That record belongs to another workspace."`

### `ProcurementDocumentRevisionUploadForm(TenantUniqueMixin, TenantModelForm)` — 2 fields
`file` (required), `change_note`. **NOT fields:** `document` (comes from the URL pk), `revision_no`,
`original_filename`, `file_size`, `sha256`, `is_approved`, `approved_by`, `approved_at`,
`uploaded_by`, `tenant`, `extracted_text`, `extraction_note`.
`clean_file()` — extension allow-list first, then size:
`"File type '.php' is not allowed."` ✅ and `f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB limit."`

### `ProcurementPolicyForm(TenantUniqueMixin, TenantModelForm)` — 15 fields
```
title policy_type summary body version_number previous_version applies_to owner document
effective_from next_review_on threshold_amount threshold_basis threshold_currency
requires_acknowledgment
```
Required: **`title`, `policy_type`, `version_number`**.
**NOT fields:** `tenant`, `number`, `status`, `published_at`, `created_by`, timestamps.
`previous_version` excludes `self.instance.pk` on edit; `empty_label`s are
`"- first version -"` / `"- the whole workspace -"` / `"- not labelled -"` / `"- none -"`.
`threshold_currency` is `Currency.objects.filter(is_active=True).order_by("code")` — **global,
never tenant-filtered**. `clean()` → `_reject_foreign(["previous_version","applies_to","document"])`.

### `KnowledgeResourceForm(TenantUniqueMixin, TenantModelForm)` — 11 fields
```
title resource_type category audience summary body tags is_featured owner document review_on
```
Required: **`title`, `resource_type`, `category`, `audience`**.
**NOT fields:** `tenant`, `number`, `status`, `usage_count`, `last_used_at`, `created_by`,
timestamps, and **no `file`**. `clean()` → `_reject_foreign(["document"])`.

---

## 6. Views — 33 routes, decorators, templates, context keys

`crud_list` always adds `object_list`, `page_obj`, `q` and paginates at **15**.
`crud_create`/`crud_edit` render `form`, `is_edit` (+ `obj` on edit).
Decorator order is `@login_required` → `@tenant_admin_required` → `@require_POST` → view, so for an
**admin-gated verb a non-admin GET is 403 (not 405)** and an **admin GET is 405**. ✅ measured.

### 6.1 `ProcurementDocument` — `templates/procurement/documentknowledge/document/*.html`

| url name | path | decorators | template | context |
|---|---|---|---|---|
| `pdocument_list` | `/procurement/documents/` | login | `document/list.html` | `object_list`, `page_obj`, `q`, `doc_type_choices`, `status_choices`, `classification_choices`, `expiry_choices`, `suppliers`, `owners`, `stats{total,active,expiring,expired,unapproved}`, `search_note`, **`classification_note`** |
| `pdocument_create` | `documents/add/` | login | `document/form.html` | `form`, `is_edit=False`, `search_note`, **`classification_note`** |
| `pdocument_reindex` | `documents/reindex/` | login+**admin**+POST | redirect → `pdocument_list` | — |
| `pdocument_run_reminders` | `documents/run-reminders/` | login+POST | redirect → `pdocument_list` | — |
| `pdocument_detail` | `documents/<pk>/` | login | `document/detail.html` | `obj`, `revisions`, `current_revision`, `policies`, `knowledge_resources`, `can_upload`, **`can_release`**, `lock_holder`, `search_note`, **`classification_note`** |
| `pdocument_edit` | `documents/<pk>/edit/` | login | `document/form.html` | `form`, `obj`, `is_edit=True`, `search_note`, `classification_note` |
| `pdocument_delete` | `documents/<pk>/delete/` | login+**admin**+POST | redirect | — |
| `pdocument_checkout` | `documents/<pk>/checkout/` | login+POST | redirect → detail | — |
| `pdocument_release` | `documents/<pk>/release/` | login+POST | redirect → detail | — |
| `pdocument_activate` | `documents/<pk>/activate/` | login+**admin**+POST | redirect → detail | — |
| `pdocument_supersede` | `documents/<pk>/supersede/` | login+**admin**+POST | redirect → detail | — |
| `pdocument_archive` | `documents/<pk>/archive/` | login+**admin**+POST | redirect → detail | — |
| `pdocument_revision_upload` | `documents/<pk>/revisions/add/` | login | `revision/form.html` | `form`, `is_edit=False`, `document`, `upload_note` |

`_document_qs` pre-narrows before `crud_list`: `readable_document_q(request.user)` +
`.defer("extracted_text")` + `select_related("supplier","owner")` (**two** relations only), then
`?expiry=` (allow-list of the four `EXPIRY_FILTER_CHOICES` values) and `?tag=` (`tags__icontains`).
`crud_list` filters: `doc_type`, `status`, `classification` (enum-guarded) and `supplier`→
`supplier_id`, `owner`→`owner_id` (`is_int=True`).
`search_fields = ("number","title","description","tags")` **plus `"extracted_text"` only when
`len(q.strip()) >= FILE_TEXT_SEARCH_MIN_CHARS` (= 4)**.
`stats` is computed over the **read-narrowed** base, so tiles and rows agree for a non-admin.

Verb rules (each refuses with `messages.error` + a redirect, never a 500, never a silent write):

| verb | rule |
|---|---|
| `pdocument_checkout` | already yours → info; held by someone → error naming them; `archived` → error; else stamp `checked_out_by`/`checked_out_at` |
| `pdocument_release` | not checked out → info; not the holder and not an admin → error; else clear both columns (a forced release is audited with `released_from`) |
| `pdocument_activate` | already `active` → info; else any → `active` |
| `pdocument_supersede` | already `superseded` → info; **not `active` → refused**; else `active` → `superseded` |
| `pdocument_archive` | already `archived` → info; else any → `archived` |
| `pdocument_delete` | **refuses while `current_revision_no != 0`** → 302 to *detail*, row survives ✅; a 0-pointer document → `crud_delete` → 302 to *list*, row gone ✅ |
| `pdocument_reindex` | candidates = `extracted_text=""` AND pointer ≠ 0 AND `Exists(pointed-at revision, is_approved=True, extraction_note="")`; `[:REINDEX_ROW_CAP]` (**25**); one batched query resolves all pointers; `time.monotonic()` budget `REINDEX_TIME_BUDGET_SECONDS` (20 s) checked *between* documents; each write is a **conditional** `.update()` filtered on `pk, tenant, extracted_text="", current_revision_no=<the one read for>`; message `"Re-indexed N document(s); M could not be read…"` + `" This run was capped — press Re-index again to continue."` when `ran_out_of_time or len(candidates) == 25` |
| `pdocument_run_reminders` | `run_document_reminders_audited`; message `"Reminder run complete: R alert(s) raised, S skipped…"` |

### 6.2 `ProcurementDocumentRevision` — `.../revision/*.html`

| url name | path | decorators | template | context |
|---|---|---|---|---|
| `pdocrevision_list` | `/procurement/document-revisions/` | login | `revision/list.html` | `object_list`, `page_obj`, `q`, `documents`, `approval_choices`, `stats{total,approved,pending}`, `revision_note` |
| `pdocrevision_detail` | `document-revisions/<pk>/` | login | `revision/detail.html` | `obj`, `document`, `is_current`, `revision_note` |
| **`pdocrevision_download`** | `document-revisions/<pk>/download/` | login (**GET**) | `FileResponse` | — |
| `pdocrevision_approve` | `document-revisions/<pk>/approve/` | login+**admin**+POST | redirect → *document* detail | — |
| `pdocrevision_delete` | `document-revisions/<pk>/delete/` | login+POST | redirect → *document* detail | — |

**There is no `pdocrevision_edit`** — asserting `NoReverseMatch` for it is a legitimate test.

`_revision_qs` = `filter(tenant=…, document__tenant=…)` **double scope** +
`readable_document_q(user, "document__")` + `select_related("document","uploaded_by","approved_by")`;
the register additionally `.defer("extracted_text", "document__extracted_text")`.
`search_fields = ("document__number","document__title","change_note","sha256")`.
Filters: `document`→`document_id` (`is_int=True`), `approved`→`is_approved`.
`documents` facet = `.only("pk","number","title").order_by("number")[:DOCUMENT_FACET_CAP]` (**200**),
narrowed by the same read rule — ✅ it is **empty** for a member who may read nothing.
**`stats` is NOT read-narrowed** (`Revisions.py:169-170` builds `base` off `tenant` +
`document__tenant` only, unlike `pdocument_list`, which narrows its own base with
`readable_document_q` at `Documents.py:166-167`). ✅ measured: a member who may read nothing still
sees `stats == {"total": 1, "approved": 1, "pending": 0}` above an empty register — a **counting
oracle over confidential revisions**, the residue of I5.
**Reported to the parent as a finding; do NOT write a test that enshrines the leaky number.**
Omit any member-facing `stats` assertion on this register for now; once the base is narrowed, the
assertion becomes `stats["total"] == 0` for `member_client` with only confidential documents
present. The `documents` facet on the same page IS narrowed and is safe to assert (empty).

`pdocrevision_download` — ✅ `200`, `Content-Disposition` contains `attachment`,
`X-Content-Type-Options == "nosniff"`; cross-tenant → **404**; a member on a confidential parent →
**404**; `dk_revision_no_file_a` → **302** back to `pdocrevision_detail` with an error message.
Close the response in the test (`resp.close()`) — it is a streaming `FileResponse`.

`pdocument_revision_upload` guards, in order: no tenant → redirect; parent not readable /
other tenant → **404** ✅; `archived` → 302 to document detail ✅; held by someone else → 302 naming
them. Happy path ✅: revision `r1`, `is_approved=False`, **pointer stays 0**, document stays
`draft`, `sha256`/`file_size`/`original_filename` measured from the upload, text extracted,
`extraction_note == ""`, 302 to the document detail.

`pdocrevision_approve` — already approved → info, **no write**; `revision_no <=
current_revision_no` → refused ✅ (re-approving r1 after r2 leaves the pointer at 2); happy path ✅
moves the pointer, copies the revision text into the parent's `extracted_text`, lifts `draft` →
`active`, writes only `["is_approved","approved_by","approved_at"]` on the revision.

`pdocrevision_delete` — both guards run **inside `transaction.atomic()` under
`select_for_update()` on the parent** and the revision is re-read there (I3). Approved → refused ✅
(row survives); current → refused; pending & non-current → deleted ✅. Not admin-gated: a
**member POST succeeds (302)** ✅.

### 6.3 `ProcurementPolicy` — `.../policy/*.html`

| url name | path | decorators | template | context |
|---|---|---|---|---|
| `ppolicy_list` | `/procurement/procurement-policies/` | login | `policy/list.html` | `object_list`, `page_obj`, `q`, `policy_type_choices`, `status_choices`, `org_units`, `review_choices`, `stats{total,published,draft,review_due}`, `advisory_note` |
| `ppolicy_create` | `…/add/` | login | `policy/form.html` | `form`, `is_edit=False`, `advisory_note` |
| `ppolicy_detail` | `…/<pk>/` | login | `policy/detail.html` | `obj`, `advisory_note`, `supersedes`, `superseded_by_rows` — **no `is_review_due` key** (M15) |
| `ppolicy_edit` | `…/<pk>/edit/` | login | `policy/form.html` | `form`, `obj`, `is_edit=True`, `advisory_note` |
| `ppolicy_delete` | `…/<pk>/delete/` | login+**admin**+POST | redirect | — |
| `ppolicy_publish` | `…/<pk>/publish/` | login+**admin**+POST | redirect → detail | — |
| `ppolicy_archive` | `…/<pk>/archive/` | login+**admin**+POST | redirect → detail | — |

`_policy_qs` = `filter(tenant=…)` + `select_related("applies_to","owner","document",
"threshold_currency")`, then `?review=due` → `next_review_on__lte=localdate()`.
`search_fields = ("number","title","summary","body")`; filters `policy_type`, `status`,
`org_unit`→`applies_to_id` (`is_int=True`). `REVIEW_CHOICES = [("due", "Review due")]` — the label
is **"Review due"**, not "Review overdue" (M13).
`superseded_by_rows = obj.superseded_by.filter(tenant_id=obj.tenant_id)[:SUPERSEDED_BY_CAP]` (10).

`ppolicy_delete` — ✅ refuses while `obj.attestations.count()` is non-zero (302 to detail, row
survives); otherwise `crud_delete` (302 to list).
`ppolicy_publish` — already published → info, no write; **archived → refused**; happy path ✅
`draft` → `published`, stamps `published_at`, and **archives the predecessor when the predecessor
is itself published** (v3 published → v2 archived), predecessor re-fetched with an explicit
`tenant_id` filter under `select_for_update`, two audit rows (`policy_publish`,
`policy_superseded`).
`ppolicy_archive` — already archived → info; else any → `archived`, **`published_at` left alone**.

### 6.4 `KnowledgeResource` — `.../knowledgeresource/*.html`

| url name | path | decorators | template | context |
|---|---|---|---|---|
| `knowledgeresource_list` | `/procurement/knowledge/` | login | `knowledgeresource/list.html` | `object_list`, `page_obj`, `q`, `resource_type_choices`, `category_choices`, `audience_choices`, `status_choices`, `featured_choices`, `featured`, `stats{total,published,featured,used}`, `library_note` |
| `knowledgeresource_create` | `knowledge/add/` | login | `…/form.html` | `form`, `is_edit=False`, `library_note` |
| `knowledgeresource_detail` | `knowledge/<pk>/` | login | `…/detail.html` | `obj`, `library_note`, `document` — **no `is_review_due` key** (M15) |
| `knowledgeresource_edit` | `knowledge/<pk>/edit/` | login | `…/form.html` | `form`, `obj`, `is_edit=True`, `library_note` |
| `knowledgeresource_delete` | `knowledge/<pk>/delete/` | login+POST | redirect → list | — |
| `knowledgeresource_publish` | `knowledge/<pk>/publish/` | login+POST | redirect → detail | — |
| `knowledgeresource_archive` | `knowledge/<pk>/archive/` | login+POST | redirect → detail | — |
| `knowledgeresource_use` | `knowledge/<pk>/use/` | login+POST | redirect → detail | — |

`_resource_qs` = `filter(tenant=…)` and **nothing else — no `select_related` at all** (I14).
`search_fields = ("number","title","summary","body","tags")`; five filters `resource_type`,
`category`, `audience`, `status`, `featured`→`is_featured`.
`featured` shelf = `status="published", is_featured=True`, `[:FEATURED_CAP]` (6), **not** paginated.
`knowledgeresource_detail` = `.defer("document__extracted_text").select_related("owner","document",
"created_by")`.
`knowledgeresource_use` — `archived` → refused ✅ (counter unchanged at 0);
`usage_count >= USAGE_COUNT_CEILING` (2 147 483 647) → `last_used_at` moves, counter does not,
`messages.info` (M24/Q2); otherwise atomic `F("usage_count") + 1` → ✅ 7 becomes **8**, redirect to
the resource's own detail page (**never** a `file.url`).
`knowledgeresource_publish` — an **archived** resource may be published again (unlike a policy).
None of these four is admin-gated: ✅ a member POST succeeds (302) on all four.

---

## 7. Regression assertions for the review worklist

Pin these by name; each is the exact thing a fix introduced.

| ID | test to write | asserts |
|---|---|---|
| **C1** | `test_dk_revision_download_is_authenticated_tenant_scoped_and_an_attachment` | 200 + `attachment` in `Content-Disposition` + `X-Content-Type-Options == "nosniff"`; anonymous → 302 to `/login/`; `client_a` on `dk_revision_b` → **404**; `dk_revision_no_file_a` → 302 + message |
| **C2** | `test_dk_revision_register_document_facet_is_capped_and_three_columns` | `len(context["documents"]) <= DOCUMENT_FACET_CAP`; the facet is empty for a member who may read nothing |
| **I1** | `test_dk_current_revision_ignores_an_unapproved_pointer` | force `current_revision_no=2` with r2 pending → `document.current_revision is None`. (`r2.is_current` stays `True` — by design.) |
| **I3** | `test_dk_revision_delete_refuses_an_approved_or_current_revision` | approved → 302 + row survives + message contains `"approved"`; pending non-current → deleted |
| **I4** | `test_dk_reindex_writes_only_while_the_pointer_is_unchanged` | move `current_revision_no` (or set `extracted_text` non-empty) between selection and write → the row is **skipped**, the old text is never installed |
| **I5** | `test_dk_member_cannot_see_confidential_or_restricted_*` (register / detail / `?q=` / facet / revision register / download / every verb) | ✅ member register shows **only** `dk_document_public_a` + `dk_document_confidential_member_a`; `?q=zephyrindemnity` and `?q=quillbaseline` → **0 rows**; `?q=harborcoverage` → 1 row; detail/verbs → 404; `stats.total == 2` |
| **I6/I8** | `test_dk_document_delete_activate_supersede_archive_are_admin_only` | member POST → **403** on all four; member POST on `checkout`/`release`/`run_reminders` → 302 (not gated) |
| **I7** | `test_dk_policy_delete_is_admin_only_and_refuses_while_attestations_exist` | member → 403; admin with `dk_attestation_a` → 302 to detail, policy survives, message mentions `"acknowledgement record"` |
| **I9** | `test_dk_extract_document_text_never_raises_and_is_bounded` | a `.txt` over `EXTRACT_MAX_CHARS` truncates; a `.png`/`.zip` → `("", NOTE_NO_TEXT_LAYER)`; a corrupt `.pdf` → `("", NOTE_BAD_FILE)`; `MAX_EXTRACT_PAGES == 500` |
| **I12** | `test_dk_reindex_is_capped_at_25_rows_and_reports_more_remain` | 26 candidates → exactly 25 indexed, message contains `"press Re-index again"`; `REINDEX_ROW_CAP == 25`; `REINDEX_TIME_BUDGET_SECONDS == 20` |
| **I13** | `test_dk_run_document_reminders_second_press_costs_two_queries` | ✅ `django_assert_max_num_queries(2)` around the **direct** call; `{"raised": 0, "skipped_open": 3}` and no new alerts |
| **I14** | `test_dk_registers_defer_extracted_text` | ✅ measured off `response.context["object_list"].query`: documents `deferred_loading == (frozenset({"extracted_text"}), True)` and `select_related == {"supplier": {}, "owner": {}}`; revisions `deferred_loading == (frozenset({"extracted_text", "document__extracted_text"}), True)`; knowledge resources `select_related is False` |
| **I15** | `test_dk_file_text_is_searched_only_from_four_characters` | ✅ `?q=har` → 0 rows; `?q=harb` → the public document; boundary == `FILE_TEXT_SEARCH_MIN_CHARS` |
| **I16** | `test_dk_document_meta_indexes_include_tenant_review_on` | `("tenant","review_on")` present with name `prc_pdoc_tnt_review_idx` |
| **M2** | `test_dk_reindex_skips_a_revision_that_already_carries_an_extraction_note` | a candidate whose current revision has a non-empty `extraction_note` is never selected |
| **M5** | `test_dk_policy_detail_successors_are_tenant_filtered` | `superseded_by_rows` never contains a foreign-tenant row |
| **M15** | `test_dk_policy_and_resource_detail_expose_no_is_review_due_context_key` | `"is_review_due" not in response.context` on both detail views |
| **M16** | `test_dk_knowledge_resource_has_no_has_been_used_attribute` | `not hasattr(KnowledgeResource, "has_been_used")` |
| **M20** | `test_dk_revision_meta_has_a_single_index` | index names == `{"prc_pdrev_tnt_appr_idx"}` |
| **M22** | `test_dk_document_detail_caps_its_three_reverse_panels` | ✅ `DETAIL_FAN_OUT_CAP == 50`; 52 revisions → exactly **50** in `context["revisions"]` |
| **M24** | `test_dk_use_refuses_at_the_usage_count_ceiling` | at `USAGE_COUNT_CEILING` the counter does not move, `last_used_at` does |
| **I11** | `test_dk_document_detail_computes_can_release_and_can_upload` | ✅ measured on `dk_document_locked_a` (held by `member_user`): holder `member_client` → `can_release=True`, `can_upload=True`, `lock_holder == member_user`; `client_a` (admin, not the holder) → `can_release=True` (force), **`can_upload=False`**; on the unlocked `dk_document_active_a` → `can_release=False`, `can_upload=True`, `lock_holder is None` |

---

## 8. Negative input, pagination, N+1 (all ✅ measured)

**Junk filter params return 200 with the FULL, un-narrowed register** on every one of the four:

```
documents      ?supplier=abc | ?supplier=0 | ?supplier=<25 nines> | ?owner=abc
               ?doc_type=nope | ?status=nope | ?classification=nope | ?expiry=nope | ?tag=
revisions      ?document=abc | ?approved=maybe
policies       ?org_unit=abc | ?review=nope | ?policy_type=nope
knowledge      ?featured=maybe | ?category=nope | ?audience=nope
```

**Pagination** (`per_page = 15`, `dk_documents_page2_a` = 16 rows): `?page=1` → 15 rows;
`?page=2` → 1 row; **`?page=999` / `?page=-1` / `?page=0` → the LAST page (2), status 200 — not a
404**; `?page=abc` → page 1. `page_obj.window` carries the ellipsis list.

**Query budgets** — measured with a full fixture set on SQLite; they are flat in the row count
(page 1 and page 2 both cost the same). Use these as `django_assert_max_num_queries` ceilings
(they include session + user + tenant + context processors):

| view | measured | suggested ceiling |
|---|---|---|
| `pdocument_list` (page 1 **and** page 2) | 12 | 14 |
| `pdocument_detail` | 11 | 13 |
| `pdocrevision_list` | 11 | 13 |
| `pdocrevision_detail` | 8 | 10 |
| `ppolicy_list` | 11 | 13 |
| `ppolicy_detail` | 9 | 11 |
| `knowledgeresource_list` | 11 | 13 |
| `knowledgeresource_detail` | 8 | 10 |
| `pdocument_create` / `ppolicy_create` form | 12 | 14 |
| `knowledgeresource_create` form | 9 | 11 |
| `pdocument_revision_upload` GET | 8 | 10 |

The N+1 test that matters: add **10 more rows** to a register and assert the count is unchanged
(the chained `__str__` FK hops — `PurchaseOrder.__str__` → `vendor`, `revision.document.number`,
`policy.threshold_currency.code` — are exactly what `select_related` is there to absorb).

---

## 9. Authz ladder (✅ measured, whole matrix)

`reverse("accounts:login") == "/login/"`; anonymous on **any** of the 33 → `302` whose `Location`
starts with `/login/`, and nothing mutates. ✅ measured across **66** requests (GET *and* POST on
all 33 routes): zero non-conforming.

| verb | member POST | member GET | admin GET |
|---|---|---|---|
| `pdocument_delete` / `_activate` / `_supersede` / `_archive` / `_reindex` | **403** | 403 | 405 |
| `pdocrevision_approve` | **403** | 403 | 405 |
| `ppolicy_delete` / `_publish` / `_archive` | **403** | 403 | 405 |
| `pdocument_checkout` / `_release` / `_run_reminders` | 302 | 405 | 405 |
| `pdocrevision_delete` | 302 | 405 | 405 |
| `knowledgeresource_delete` / `_publish` / `_archive` / `_use` | 302 | 405 | 405 |

CSRF: `Client(enforce_csrf_checks=True)` + `force_login` → **403** on every POST verb, and nothing
changes; the same client still GETs 200 (the L44 pair).

**Cross-tenant (✅ all 404, never 403 and never a redirect):** `client_a` on `dk_document_b`
(detail / edit / delete / checkout / release / activate / supersede / archive / revisions-add),
`dk_revision_b` (detail / **download** / approve / delete), `dk_policy_b` (detail / edit / delete /
publish / archive), `dk_resource_b` (detail / edit / delete / publish / archive / use).
A's registers never contain B's rows.

**Crafted POSTs** (302 or 200-with-errors, never a saved cross-tenant row):
`ProcurementDocumentForm` with `supplier=dk_supplier_b.pk` → `"Select a valid choice"` /
`"That record belongs to another workspace."`; `ProcurementPolicyForm` with
`previous_version=dk_policy_b.pk` or `document=dk_document_b.pk`; `KnowledgeResourceForm` with
`document=dk_document_b.pk`.

---

## 10. Message fragments safe to assert

Assert **substrings without the em dash** (`—` U+2014 appears in several messages):
`"approved revision chain"` · `"acknowledgement record"` · `"only moves forward"` ·
`"is approved, so it stays on the record"` · `"currently points at"` ·
`"has this document checked out"` · `"holds this checkout"` ·
`"is archived, so it does not take new revisions"` · `"is archived and cannot be published again"` ·
`"is archived, so it is not counted as in use"` · `"Re-indexed"` ·
`"press Re-index again to continue"` · `"Reminder run complete"` · `"is now published"` ·
`"Nothing was deleted"` · `"File type '.php' is not allowed."`
Read them with `list(response.wsgi_request._messages)` after `follow=True`, or
`django.contrib.messages.get_messages(response.wsgi_request)`.

---

## 11. Where the code disagrees with the stale build contract

`.claude/tasks/contract-procurement-6.19.md` is the BUILD contract. Every line below is a place a
test written from it would fail for the wrong reason.

| # | Stale build contract says | The code does |
|---|---|---|
| 1 | 32 url names | **33** — `pdocrevision_download` (`document-revisions/<pk>/download/`, GET) was added by C1 |
| 2 | `pdocument_list` context ends at `search_note` | adds **`classification_note`**; so do `pdocument_create`, `pdocument_edit` and `pdocument_detail` |
| 3 | `pdocument_detail` keys: `obj, revisions, current_revision, policies, knowledge_resources, can_upload, lock_holder, search_note` | adds **`can_release`** (I11) and `classification_note` |
| 4 | `ppolicy_detail` includes `is_review_due` | **dropped** (M15) — the template reads `obj.is_review_due` |
| 5 | `knowledgeresource_detail` includes `is_review_due` | **dropped** (M15) |
| 6 | `search_fields` for documents always includes `extracted_text` | swept **only when `len(q) >= 4`** (I15, `FILE_TEXT_SEARCH_MIN_CHARS`) |
| 7 | document list `select_related("supplier","owner","contract","purchase_order","sourcing_event")` | **`("supplier","owner")`** only, plus `.defer("extracted_text")` (I14) |
| 8 | `knowledgeresource_list` `select_related("owner","document")` | **no `select_related` at all** (I14) |
| 9 | revision register: plain `_revision_qs` | `.defer("extracted_text","document__extracted_text")`; the `documents` facet is `.only("pk","number","title")…[:200]` (C2) |
| 10 | `SEARCH_NOTE` = "Search matches the title, description, tags and any text read from the approved file…" | rewritten: "…matches the **number**, title, description and tags **always**, and the text read from the approved file **once you type four characters or more**…" |
| 11 | `REINDEX_ROW_CAP = 200` | **25** (I12), plus `REINDEX_TIME_BUDGET_SECONDS = 20`, batched pointer resolution and a conditional `.update()` (I4) |
| 12 | re-index candidates = empty text + approved current revision | **also** requires that revision's `extraction_note == ""` (M2) |
| 13 | `pdocument_delete` = `@require_POST` only | **`@tenant_admin_required`** + refuses while `current_revision_no != 0` (I6) |
| 14 | `pdocument_activate/supersede/archive` = `@require_POST` | all three **`@tenant_admin_required`** (I8) |
| 15 | `ppolicy_delete` / `ppolicy_archive` = `@require_POST` | both **`@tenant_admin_required`**; delete additionally refuses while `attestations` exist (I7, I8) |
| 16 | `current_revision` = `revisions.filter(revision_no=pointer).first()` | **`…, is_approved=True).first()`** (I1) |
| 17 | `pdocrevision_delete` reads its guards off an unlocked snapshot | both guards run under `select_for_update()` on the parent with the revision re-read inside (I3) |
| 18 | `review_choices = [("due","Review overdue")]` | **`[("due","Review due")]`** (M13) |
| 19 | `superseded_by_rows = obj.superseded_by.all()[:10]` | `.filter(tenant_id=obj.tenant_id)[:SUPERSEDED_BY_CAP]` (M5) |
| 20 | `pdocument_detail` reverse panels unbounded; `current_revision` re-fetched | all three capped at `DETAIL_FAN_OUT_CAP = 50` (M22) and `current_revision` resolved from the list in memory (M21) |
| 21 | revision indexes: `prc_pdrev_tnt_doc_idx` + `prc_pdrev_tnt_appr_idx` | only **`prc_pdrev_tnt_appr_idx`** (M20) |
| 22 | document indexes: status / doc_type / expires_on / supplier | **plus `prc_pdoc_tnt_review_idx`** on `("tenant","review_on")` (I16) |
| 23 | `KnowledgeResource.has_been_used` exists | **deleted** (M16) |
| 24 | `knowledgeresource_use` increments unconditionally | refuses at `USAGE_COUNT_CEILING = 2_147_483_647` (M24) |
| 25 | `run_document_reminders` dedupes per row under a lock | the open-alert set is read **once before the loop**; the lock is taken only where a write happens (I13) |
| 26 | `_holder_name` private to each view module | one `holder_name` in `views/_helpers.py` (M18); `readable_document_q`, `OPEN_CLASSIFICATIONS` and `CLASSIFICATION_NOTE` live there too and are new |
| 27 | classification is a label | **enforced** by `readable_document_q` on both entities — the register, `?q=`, every facet, the stat tiles, the detail page, the revision register, the download and every verb (I5) |

### Field-name traps this session already hit
* the party FK is **`supplier`**, never `vendor`;
* the revision note column is **`extraction_note`**, never `extract_note`;
* the review column is **`review_on`** on `ProcurementDocument` and `KnowledgeResource` but
  **`next_review_on`** on `ProcurementPolicy` (M14 was deliberately skipped — 6.17 already reads
  `next_review_on`);
* there is **no `uploaded_at`** on a revision — `created_at` is the upload moment;
* `ProcurementPolicy.__str__` uses the **title**, the other three use the **number**.
