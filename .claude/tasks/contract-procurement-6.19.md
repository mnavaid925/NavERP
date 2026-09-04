# Contract — Procurement 6.19 Document & Knowledge Management

**Single authority for the build.** Distilled from `.claude/tasks/todo.md` lines **2274–3133** and
**verified against the code** (see Verification log). Where the plan and the code disagreed, the code won.
Build agents work from THIS file; they do not re-read the 860-line plan.

| | |
|---|---|
| Sub-module | **6.19 Document & Knowledge Management** (Module 6, NavERP.md five bullets) |
| App | `apps/procurement` — **EXTEND** run. No scaffold, no `config/settings.py`, no `config/urls.py` edit. |
| Backend sub-package | `apps/procurement/{models,forms,views,urls}/DocumentKnowledgeManagement/` |
| Template root | `templates/procurement/documentknowledge/<entity>/{list,detail,form}.html` |
| BASE sha (Phase 4 reviews `BASE...HEAD`) | **`56ae21a9`** |
| Models (4, no fifth) | `ProcurementDocument` [PDOC-] · `ProcurementDocumentRevision` (child, no prefix) · `ProcurementPolicy` [PPOL-] · `KnowledgeResource` [PKR-] |

**Owns:** a procurement-scoped document repository with a linear approved-revision chain, a policy library, a
knowledge/templates library, `icontains` search over extracted text, expiry/review reminders into
`ProcurementAlert`.
**Defers to Module 13:** folder hierarchies (13.4), redline/diff/branching (13.2), permission matrices /
watermarking / DRM / DLP (13.7), OCR + semantic search + auto-tagging (13.5/13.6), retention auto-destruction /
legal hold / WORM (13.9/13.14), wikis (13.17). **`core.Document` is NOT touched.**
**Hard ban:** the word **"OCR"** may not appear on any 6.19 page, label, help_text or empty state. Say
"text read from the file" / "this file has no text layer".

---

## Verification log

| # | Claim in the plan | Result |
|---|---|---|
| 1 | Section is at todo.md lines 1599–2458 | **CORRECTED** — 1599–2273 is **6.16**. The 6.19 section is **2274–3133**. |
| 2 | `apps/core/utils.log_action` | **CORRECTED** — `log_action` **does not exist anywhere**. Real helper: `write_audit_log(user, obj, action, changes=None, tenant=None)` at `apps/core/utils.py:6`. Plan's body already uses it correctly. |
| 3 | Migration number is `0026` | **CORRECTED** — leaf on disk is `0025_remove_budgetmapping_...`; the **6.16 section of the same todo.md reserves `0026` for 6.16 and `0029` for 6.19**. Contradiction. **No slot is pre-reserved here** — see Concurrency. |
| 4 | `models/_base.py` star-import supplies the ORM toolkit | **CORRECTED** — it exports `F, Q, Sum` only. **`Max` and `Count` are NOT in it.** `Revisions.py` must `from django.db.models import Max`; views must `from django.db.models import Count, Q`. |
| 5 | `ProcurementDocument.sourcing_event` links to `procurement:sourcingevent_detail` | **CORRECTED** — that url name does not exist. The real one is **`procurement:event_detail`** (`urls/SourcingTendering/SourcingEvents.py:15`). |
| 6 | `ALLOWED_DOC_EXTENSIONS` = 14 extensions | **CORRECTED** — **13**: `.pdf .doc .docx .xls .xlsx .csv .txt .png .jpg .jpeg .gif .webp .zip` (`apps/core/forms/_common.py:16`). |
| 7 | `_safe_reverse` supports `url#fragment` | **VERIFIED** — `apps/core/navigation.py:1838`; `_route_name` strips `?`/`#` before `reverse()` and re-appends the suffix. 6.13 precedent `procurement:invoicevoucher_dashboard#discount` at `navigation.py:1605`. **Fragment KEPT.** |
| 8 | Four new url first segments free | **VERIFIED** — `documents/`, `document-revisions/`, `procurement-policies/`, `knowledge/` collide with nothing (full inventory dumped from `path()` calls, below). No first-position converter exists in this app. |
| 9 | `urls/__init__.py` docstring lists every segment | **CORRECTED (informational)** — the docstring inventory is **stale**: it omits `delegations/`, `eauc/`, `po-changes/`, `po-generation/`, `po-tracking/`. Use the dumped list below, and add the four new segments to that docstring at Integrate. |
| 10 | Only colour-named badges exist | **VERIFIED** — theme.css has `.badge-green .badge-red .badge-amber .badge-info .badge-muted .badge-slate` (+ `.badge-group`). `badge-success` / `-warning` / `-danger` / `-primary` / `-secondary` **CONFIRMED ABSENT** (L33). Layout classes present: `.stat-grid .stat-card .stat-icon .filter-bar .page-header`; text classes `.text-muted .text-danger .text-ok .text-warn .text-red .text-brand .text-right`. |
| 11 | Template slug is `documentknowledge` | **VERIFIED** — 6.14 = `spendanalytics`, 6.15 = `budgetcost` (short slugs). (6.13 used the long `invoicevouchermanagement`; the two most recent siblings set the convention.) Page files are bare `list.html` / `detail.html` / `form.html` inside `<submodule>/<entity>/`. |
| 12 | FK targets `core.Party`, `core.Tenant`, `core.OrgUnit`, `accounting.Currency`, `scm.SupplierContract`, `scm.PurchaseOrder`, `procurement.SourcingEvent`, `procurement.ProcurementAlert` | **ALL VERIFIED** at the exact paths the plan names. `scm.PurchaseOrder` (`apps/scm/models/ProcurementManagement/PurchaseOrders.py:15`) is the right one; `crm.PurchaseOrder` (`apps/crm/models/InventoryVendor/PurchaseOrders.py:5`) is the legacy one — **never FK that**. |
| 13 | Model names + number prefixes free | **VERIFIED** — `ProcurementDocument` / `ProcurementDocumentRevision` / `ProcurementPolicy` / `KnowledgeResource` unused anywhere in `apps/`. `PDOC` / `PPOL` / `PKR` free (29 prefixes in use, none of these). |
| 14 | Every proposed `related_name` free | **VERIFIED** — `procurement_documents`, `procurement_documents_owned`, `procurement_policies`, `procurement_policies_owned`, `procurement_knowledge_owned`, `knowledge_resources`, `revisions`, `policies`, `documents`, `superseded_by` all clear **on their target models**. |
| 15 | `core.Document.CLASSIFICATION_CHOICES` first three verbatim | **VERIFIED** — it has exactly three: `public` / `internal` / `confidential`. 6.19 appends `restricted`. |
| 16 | `MAX_UPLOAD_BYTES` = 20 MB core / 2 MB CatalogManagement | **VERIFIED** — `apps/core/forms/_common.py:22` = `20 * 1024 * 1024`; `apps/procurement/forms/CatalogManagement/UploadBatches.py:13` = `2 * 1024 * 1024`. The 2 MB one must **never** be reused. |
| 17 | `_pdf_text` lazy-import posture | **VERIFIED** — `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:418`. `pdfplumber==0.11.10` at `requirements.txt:14`. |
| 18 | `run_renewal_alerts` is the reminder-engine model | **VERIFIED** — `apps/procurement/models/ContractsManagement/Renewals.py:55` (+ `run_renewal_alerts_audited` at `:97`). Returns `{"raised": n, "skipped_open": n}`. |
| 19 | Prod MySQL / tests SQLite, so no FULLTEXT | **VERIFIED** — `config/settings.py:102` mysql, `config/settings_test.py:10` sqlite3. |
| 20 | `crud_edit(model=…, form_class=…)` | **CORRECTED** — signature also requires **`pk=pk`**. See real signatures below. |
| 21 | `tenant_admin_required` refuses a non-admin | **VERIFIED with a correction to the smoke expectation** — it raises `PermissionDenied` → **403**, not a redirect. |
| 22 | Supplier Party queryset convention | **VERIFIED** — `Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor")).distinct()` (`forms/ContractsManagement/Contracts.py:21`, `GoodsReceiptInspection/ReceiptTolerances.py:22`). `PartyRole.ROLE_CHOICES` carries both `vendor` and `supplier`. |
| 23 | `accounting.Currency` is global (no tenant column) | **VERIFIED** — `TenantModelForm` leaves it alone; narrow it by hand. `core.OrgUnit` **has** a tenant FK, so `TenantModelForm` auto-scopes it. |
| 24 | No 6.16/6.17/6.18 LIVE_LINKS keys exist | **VERIFIED** — module 6 has `6.1`–`6.15` only. `"6.19"` is appended after the `"6.15"` block. |

---

## Real signatures — quote these, do not re-invent

```python
# apps/core/utils.py:6 / :34
write_audit_log(user, obj, action, changes=None, tenant=None)   # obj may be None (engine runs)
next_number(model, tenant, prefix, width=5, field="number")

# apps/core/crud.py — qs and template are POSITIONAL; everything after * is keyword-only
crud_list(request, qs, template, *, search_fields=(), filters=(), extra_context=None, per_page=15)
crud_create(request, *, form_class, template, success_url, extra_context=None, set_tenant=True, audit=True)
crud_edit(request, *, model, pk, form_class, template, success_url, extra_context=None, audit=True)
crud_detail(request, *, model, pk, template, extra_context=None, select_related=())
crud_delete(request, *, model, pk, success_url, audit=True)
paginate(request, qs, per_page=15)          # crud_list calls it; do not call directly
as_db_int(value)                            # L11 guard, used by crud_list's is_int path

# apps/core/forms/_common.py
class TenantModelForm(forms.ModelForm):
    def __init__(self, *args, tenant=None, **kwargs)   # auto-scopes any FK whose TARGET has `tenant`
ALLOWED_DOC_EXTENSIONS = {".pdf",".doc",".docx",".xls",".xlsx",".csv",".txt",
                          ".png",".jpg",".jpeg",".gif",".webp",".zip"}      # 13
MAX_UPLOAD_BYTES = 20 * 1024 * 1024                                        # 20 MB

# apps/procurement/forms/_common.py
class TenantUniqueMixin:  ...        # mix in BEFORE TenantModelForm; stamps instance.tenant pre-full_clean
_reject_foreign(form, cleaned, names)  # -> form.add_error(name, "That record belongs to another workspace.")

# apps/procurement/models/_base.py  (star-import surface)
#   secrets, Decimal, settings, ValidationError, MaxValueValidator, MinValueValidator,
#   IntegrityError, models, transaction, F, Q, Sum, timezone, next_number,
#   ZERO, MAX_Q2, q2(value), TenantOwned, TenantNumbered
#   >>> Max and Count are NOT here. Import them explicitly. <<<
class TenantOwned(models.Model):     # tenant FK related_name="+", created_at (auto_now_add), updated_at (auto_now)
class TenantNumbered(TenantOwned):   # NUMBER_PREFIX = ""; number = CharField(20, editable=False)
                                     # save() allocates once, 5x retry-on-IntegrityError

# apps/procurement/views/_common.py  (star-import surface)
#   messages, login_required, get_object_or_404, redirect, render, timezone, require_POST,
#   crud_create, crud_delete, crud_detail, crud_edit, crud_list,
#   tenant_admin_required, write_audit_log

# apps/procurement/views/_helpers.py  — cross-sub-module helpers only
#   PROCUREMENT_CONTENT_MODELS, ACTIVITY_FEED_NOTE, procurement_activity_qs(tenant),
#   DUPLICATE_WINDOW_DAYS, DUPLICATE_ACTIVE_STATUSES  (6.19 adds nothing here)

# apps/core/decorators.py — raises PermissionDenied (403); already wraps @login_required
tenant_admin_required(view_func)

# apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:418 — copy this posture exactly
def _pdf_text(document):
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None
    if pdfplumber is None: return "", [...]
    path = getattr(document.file, "path", None) if document is not None else None
    if not path: return "", [...]
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:                       # malformed PDF — a page, not a 500
        return "", [...]
    if not (text or "").strip(): return "", [...]
    return text, []
```

### `crud_list` filter semantics (why the choice strings below are exact)
`filters` = `(get_param, orm_lookup, is_int)` tuples, applied **before** pagination.
* `is_int=True` → `as_db_int()`: non-decimal, over-range, and `0` on a `*_id`/`pk` lookup all **skip the filter** (L11).
* `is_int=False` → `{"True": True, "False": False}` mapping first, then an **enum guard**: a value not in the
  field's `choices` **skips the filter** (never empties the register). A `BooleanField` has no `choices`, so the
  guard passes it through and a junk value is caught by the `ValueError/ValidationError` except.
  **This is why the boolean facets must offer literally `"True"` / `"False"`.**
* Always provides `object_list`, `page_obj`, `q`.

---

## Sibling shape reference (6.15 `BudgetCostManagement`) — copy these idioms

**View module header** (`views/DocumentKnowledgeManagement/<Entity>.py`):
```python
"""Procurement 6.19 Document & Knowledge Management — <Entity> views. ..."""
from django.db.models import Count, Q                      # Max too, where needed

from apps.procurement.forms.DocumentKnowledgeManagement.<Entity> import <Entity>Form
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.<Entity> import <Model>
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST   = "procurement/documentknowledge/<entity>/list.html"
TEMPLATE_DETAIL = "procurement/documentknowledge/<entity>/detail.html"
TEMPLATE_FORM   = "procurement/documentknowledge/<entity>/form.html"
_ROW_RELATIONS = (...)

def _<entity>_qs(request):
    return <Model>.objects.filter(tenant=request.tenant).select_related(*_ROW_RELATIONS)

def _need_tenant(request, what):                     # only on hand-rolled write paths
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace before you {what}.")
        return redirect("dashboard:home")
    return None

@login_required
def <entity>_list(request):
    base = <Model>.objects.filter(tenant=request.tenant)
    stats = base.aggregate(total=Count("pk"), x=Count("pk", filter=Q(...)))   # ONE aggregate
    return crud_list(request, _<entity>_qs(request), TEMPLATE_LIST,
                     search_fields=(...), filters=(...), extra_context={...})

@login_required
def <entity>_detail(request, pk):
    return crud_detail(request, model=<Model>, pk=pk, template=TEMPLATE_DETAIL,
                       select_related=_ROW_RELATIONS, extra_context={...})

@login_required
def <entity>_create(request):
    return crud_create(request, form_class=<Form>, template=TEMPLATE_FORM,
                       success_url="procurement:<entity>_list", extra_context={...})

@login_required
def <entity>_edit(request, pk):
    return crud_edit(request, model=<Model>, pk=pk, form_class=<Form>,
                     template=TEMPLATE_FORM, success_url="procurement:<entity>_list",
                     extra_context={...})

@login_required
@require_POST
def <entity>_delete(request, pk):
    return crud_delete(request, model=<Model>, pk=pk, success_url="procurement:<entity>_list")
```

**POST-only verb view** (hand-rolled — refuse with a message, never a 500, never a silent no-op):
```python
@login_required
@require_POST                       # add @tenant_admin_required for privileged verbs
def <entity>_<verb>(request, pk):
    obj = get_object_or_404(<Model>, pk=pk, tenant=request.tenant)
    if <disallowed transition>:
        messages.error(request, "<why>")
        return redirect("procurement:<entity>_detail", pk=obj.pk)
    if <already in target state>:
        messages.info(request, "<idempotent note>")            # no write
        return redirect("procurement:<entity>_detail", pk=obj.pk)
    obj.<field> = <value>; obj.<stamp> = timezone.now()
    obj.save(update_fields=[..., "updated_at"])
    write_audit_log(request.user, obj, "<action>", {...})
    messages.success(request, "<what happened>")
    return redirect("procurement:<entity>_detail", pk=obj.pk)
```
Decorator order as written: `@login_required` → `@tenant_admin_required` → `@require_POST` → `def`.

**Form module** — `class <X>Form(TenantUniqueMixin, TenantModelForm)`, `TenantUniqueMixin` FIRST;
`Meta.fields` an explicit **list**; `def __init__(self, *args, tenant=None, **kwargs)` calling
`super().__init__(*args, tenant=tenant, **kwargs)`, then `if tenant is None: <narrow to .none()>; return`;
`def clean(self)` calling `super().clean()` then `_reject_foreign(self, cleaned, [...])` and `return cleaned`.

**`urls/DocumentKnowledgeManagement/<Entity>.py`**:
```python
"""Procurement 6.19 … — <Entity> URL patterns. <segment inventory + first-match-wins note>"""
from django.urls import path
from apps.procurement import views

urlpatterns = [ path("<seg>/", views.<name>, name="<name>"), ... ]   # literals BEFORE <int:pk>
```

**Template block structure** (every page):
`{% extends "base.html" %}` → `{% block title %}` → `{% block content %}` → a leading `{% comment %}` naming
the view module and **the complete context contract** → `.page-header` (h1.page-title + `.breadcrumb`
`procurement:dashboard` › sub-module › entity + a `.text-muted` note constant) → `.page-actions` →
`.stat-grid` of `.stat-card`/`.stat-icon` → `.card > .card-body > <form method="get" class="filter-bar">`
(one control per declared filter, reflecting `request.GET`, + Apply + Reset) → table with an **Actions column**
→ `{% empty %}` empty state with a "Clear filters" link → `{% include "partials/pagination.html" %}`.
Filter comparison: strings `{% if request.GET.status == val %}selected{% endif %}`; FK pks
`{{ o.pk|stringformat:"d" }}` compared the same way — **never `|slugify`**.
Form page is ONE template for create+edit driven by `is_edit`; it reads only `form`, `is_edit`, (edit) `obj`
and the note constant; per-field help keyed off `field.name`; label bound with `for="{{ field.id_for_label }}"`.

---

## Model 1 — `ProcurementDocument` [PDOC-]
`models/DocumentKnowledgeManagement/Documents.py` · base `TenantNumbered` · `NUMBER_PREFIX = "PDOC"`
Bullets **1 Central Document Repository**, **2 Version Control (parent half)**, **5 Full-Text Search & Indexing**.

| Field | Type + args | null/blank | Default | Notes |
|---|---|---|---|---|
| `title` | `CharField(max_length=200)` | — | — | required |
| `doc_type` | `CharField(max_length=16, choices=DOC_TYPE_CHOICES)` | — | `"other"` | |
| `description` | `TextField(blank=True)` | blank | `""` | |
| `tags` | `CharField(max_length=255, blank=True, help_text="Comma-separated keywords")` | blank | `""` | normalized in `clean()`; **not** a Tag table |
| `classification` | `CharField(max_length=14, choices=CLASSIFICATION_CHOICES)` | — | `"internal"` | |
| `status` | `CharField(max_length=12, choices=STATUS_CHOICES)` | — | `"draft"` | **verb-driven, NOT on the form** |
| `owner` | `FK(settings.AUTH_USER_MODEL, SET_NULL, related_name="procurement_documents_owned")` | null+blank | — | |
| `supplier_visible` | `BooleanField(help_text="Vendors may see this in the 6.4 portal when that page ships")` | — | `False` | flag only; 6.4 owns the page |
| `effective_date` | `DateField` | null+blank | — | |
| `expires_on` | `DateField` | null+blank | — | |
| `review_on` | `DateField` | null+blank | — | |
| `retention_until` | `DateField(help_text="Hold until this date. Nothing is deleted automatically.")` | null+blank | — | a flag, never an action |
| `current_revision_no` | `PositiveSmallIntegerField(editable=False)` | — | `0` | **integer pointer, not a circular FK**; `0` = none approved yet |
| `checked_out_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL, editable=False, related_name="+")` | null+blank | — | advisory lock |
| `checked_out_at` | `DateTimeField(editable=False)` | null+blank | — | |
| `extracted_text` | `TextField(blank=True, editable=False)` | blank | `""` | **denormalized search copy** of the current approved revision |
| `supplier` | `FK("core.Party", SET_NULL, related_name="procurement_documents")` | null+blank | — | |
| `contract` | `FK("scm.SupplierContract", SET_NULL, related_name="procurement_documents")` | null+blank | — | |
| `purchase_order` | `FK("scm.PurchaseOrder", SET_NULL, related_name="procurement_documents")` | null+blank | — | the **SCM** one, never `crm.PurchaseOrder` |
| `sourcing_event` | `FK("procurement.SourcingEvent", SET_NULL, related_name="documents")` | null+blank | — | |
| `created_by` | `FK(settings.AUTH_USER_MODEL, SET_NULL, editable=False, related_name="+")` | null+blank | — | |

Four real columns, **explicitly not a GenericForeignKey** — a GFK is not tenant-filterable at the queryset
level (an IDOR surface) and the register must facet on them. All FKs declared **by string**; no cross-app
model imports at module level.

### Choices — exact `(value, "Label")` pairs
```python
DOC_TYPE_CHOICES = [("quote","Quote"),("specification","Specification"),("warranty","Warranty"),
    ("certificate","Certificate"),("insurance","Certificate of Insurance"),("sow","Statement of Work"),
    ("drawing","Drawing"),("correspondence","Correspondence"),("policy","Policy Document"),
    ("template","Template"),("other","Other")]
CLASSIFICATION_CHOICES = [("public","Public"),("internal","Internal"),
    ("confidential","Confidential"),("restricted","Restricted")]     # first 3 verbatim from core.Document
STATUS_CHOICES = [("draft","Draft"),("active","Active"),("superseded","Superseded"),("archived","Archived")]
EXPIRY_FILTER_CHOICES = [("expiring","Expiring soon"),("expired","Expired"),
    ("review_due","Review due"),("over_retention","Past retention")]   # a register facet, NOT a column
EXPIRY_WARN_DAYS = 30
REMINDER_WINDOW_DAYS = 30
REINDEX_ROW_CAP = 200
STATUS_CSS = {"draft":"badge-muted","active":"badge-green","superseded":"badge-amber","archived":"badge-slate"}
CLASSIFICATION_CSS = {"public":"badge-info","internal":"badge-slate",
                      "confidential":"badge-amber","restricted":"badge-red"}
```

### Meta / behaviour
* `ordering = ["-created_at", "-id"]` · `unique_together = ("tenant", "number")`
* `indexes` (all ≤ 30 chars): `("tenant","status")` `prc_pdoc_tnt_status_idx`; `("tenant","doc_type")`
  `prc_pdoc_tnt_type_idx`; `("tenant","expires_on")` `prc_pdoc_tnt_expiry_idx`; `("tenant","supplier")`
  `prc_pdoc_tnt_sup_idx`
* `verbose_name = "Procurement Document"` / `verbose_name_plural = "Procurement Documents"`
* `__str__` → `f"{self.number or 'PDOC'} · {self.title}"`
* Properties: `tag_list`, `status_css`, `classification_css` (both with a `badge-slate` fallback),
  `is_expired`, `is_expiring`, `is_review_due`, `is_over_retention`,
  `is_checked_out` (`checked_out_by_id is not None`),
  `current_revision` → `self.revisions.filter(revision_no=self.current_revision_no).first()` when
  `current_revision_no` else `None` (**reverse accessor — no child import, no cycle**)
* `clean()`: normalize `tags` (lowercase, strip, dedupe, re-join `", "`); cross-tenant `_id` backstop on
  `supplier`/`contract`/`purchase_order`/`sourcing_event` → `"That record belongs to another workspace."`;
  reject `expires_on < effective_date`

### Reminder engine — module-level in the same file, NOT a fifth model
```python
expiring_documents(tenant, *, on=None)      # -> [{"document", "days_left", "reason"}]
                                            #    expires_on/review_on within REMINDER_WINDOW_DAYS or past,
                                            #    status__in=("draft","active")
run_document_reminders(tenant, user)        # -> {"raised": n, "skipped_open": n}
@transaction.atomic
run_document_reminders_audited(tenant, user)  # scan + write_audit_log(user, None, "document_reminders_run", {...})
```
`run_document_reminders` copies `ContractsManagement/Renewals.py:55` exactly: per row
`with transaction.atomic():` → `ProcurementDocument.objects.select_for_update().get(pk=…)` →
dedupe against an existing `ProcurementAlert` with the same `link_url` and
`status__in=("open","acknowledged")` (or `ProcurementAlert.OPEN_STATUSES`) → else create with
`kind="deadline"`, `severity="critical" if days_left <= 7 else "warning"`, `status="open"`,
`link_url=f"/procurement/documents/{pk}/"` (**internal path only** — `ProcurementAlert.clean()` rejects
absolute / `javascript:` values), `due_at=None`.
Docstring states plainly: **no scheduler and no mail worker exist** — this is a user-pressed verb and the
alert inbox is the channel.

---

## Model 2 — `ProcurementDocumentRevision` (child, **no** prefix)
`models/DocumentKnowledgeManagement/Revisions.py` · base `TenantOwned` · bullet **2 Version Control**

| Field | Type + args | null/blank | Default | Notes |
|---|---|---|---|---|
| `document` | `FK("procurement.ProcurementDocument", CASCADE, related_name="revisions")` | — | — | |
| `revision_no` | `PositiveSmallIntegerField(editable=False)` | — | `1` | allocated under a parent row lock |
| `file` | `FileField(upload_to="procurement/documents/%Y/%m/", help_text="Serve with Content-Disposition: attachment and keep MEDIA_ROOT outside any executable path.")` | — | — | the `RfxManagement/Responses.py` idiom |
| `original_filename` | `CharField(max_length=255, blank=True, editable=False)` | blank | `""` | |
| `file_size` | `PositiveIntegerField(editable=False)` | — | `0` | |
| `sha256` | `CharField(max_length=64, blank=True, editable=False, help_text="Integrity checksum of the stored bytes")` | blank | `""` | `hashlib` only. Page says "checksum", **never** "tamper-proof"/"WORM" |
| `change_note` | `CharField(max_length=255, blank=True)` | blank | `""` | **the only user-typed field on this model** |
| `is_approved` | `BooleanField(editable=False)` | — | `False` | |
| `approved_by` | `FK(AUTH_USER_MODEL, SET_NULL, editable=False, related_name="+")` | null+blank | — | |
| `approved_at` | `DateTimeField(editable=False)` | null+blank | — | |
| `uploaded_by` | `FK(AUTH_USER_MODEL, SET_NULL, editable=False, related_name="+")` | null+blank | — | |
| `extracted_text` | `TextField(blank=True, editable=False)` | blank | `""` | **the text of record**, capped at ingest |
| `extraction_note` | `CharField(max_length=255, blank=True, editable=False)` | blank | `""` | the honest warning — what makes the no-OCR contract visible |

**No separate `uploaded_at`** — `TenantOwned.created_at` IS the upload moment. Say so in the docstring so the
templates do not invent a second name.

### Meta / behaviour
* `ordering = ["-revision_no", "-id"]`
* `unique_together = ("tenant", "document", "revision_no")` — the DB backstop for the allocation race
* `indexes`: `("tenant","document")` `prc_pdrev_tnt_doc_idx`; `("tenant","is_approved")` `prc_pdrev_tnt_appr_idx`
* `__str__` → `f"{self.document.number} r{self.revision_no}"`
* Property `is_current` → `self.revision_no == self.document.current_revision_no`
* `clean()`: same-tenant `_id` guards on `document` (use `_id` + an explicit queryset lookup, never a bare
  `self.document.tenant_id`, which raises `RelatedObjectDoesNotExist` on an unset FK)

### Module-level helpers (same file)
```python
EXTRACT_MAX_CHARS = 200_000
PLAIN_TEXT_EXTENSIONS = {".txt", ".csv"}
file_sha256(upload)             # hex digest streamed over upload.chunks(); upload.seek(0) BEFORE and AFTER
extract_document_text(revision) # -> (text, note)
```
`extract_document_text` copies `_pdf_text`'s posture exactly — lazy `import pdfplumber` inside the function
with `except ImportError: pdfplumber = None`; every return truncated to `EXTRACT_MAX_CHARS`; plain-text
extensions decoded directly with `errors="replace"`. Exact note strings:

| Condition | `note` |
|---|---|
| pdfplumber absent | `"Text extraction is not installed on this server - this file is searchable by its title, description and tags only."` |
| `file.path` missing | `"The stored file could not be read back."` |
| malformed PDF (broad `except Exception`) | `"That file could not be read."` |
| extract blank | `"This file has no text layer, so there is no text to search."` |

`from django.db.models import Max` is required here (not in `_base.py`).

### THE REVISION CHAIN — numbered rules (the riskiest part of this sub-module)

1. **Immutability is structural, not a `save()` guard.** (a) No edit url, no edit view, no edit template —
   documented exemption in the url module docstring (`CostForecast` / `SpendReportSnapshot` precedent);
   (b) every column except `change_note` is `editable=False`, so no `ModelForm` can surface it;
   (c) the only form is `ProcurementDocumentRevisionUploadForm`, create path only;
   (d) the only post-create write is approve's `save(update_fields=["is_approved","approved_by","approved_at"])`.
2. **Upload guards, in this order** — (1) `request.tenant is None` → refuse (`_need_tenant`);
   (2) `document.status == "archived"` → refuse with a message;
   (3) `document.checked_out_by_id not in (None, request.user.pk)` → refuse, **naming the holder**.
3. **Allocation under a lock.** Inside `transaction.atomic()`:
   `locked = ProcurementDocument.objects.select_for_update().get(pk=document.pk, tenant=request.tenant)`;
   `revision_no = (locked.revisions.aggregate(m=Max("revision_no"))["m"] or 0) + 1`; compute
   `sha256` / `file_size` / `original_filename` **before** `save()`; save; then run `extract_document_text`
   and store `extracted_text` + `extraction_note` on the **revision** via `save(update_fields=[...])`.
   `unique_together` is the backstop — catch `IntegrityError`, retry **once** (the `TenantNumbered.save()`
   idiom), then surface an honest error.
4. **Uploading NEVER moves `current_revision_no`.** A new revision lands `is_approved=False`. This is the
   literal NavERP bullet: only the latest *approved* version is the accessible one.
5. **Approve** (`@login_required` + `@tenant_admin_required` + `@require_POST`):
   (a) 404 unless `revision.tenant == request.tenant` **and** `revision.document.tenant == request.tenant`
   (double scope — never trust the child alone);
   (b) already `is_approved` → idempotent `messages.info`, redirect, **no write**;
   (c) **`revision.revision_no <= document.current_revision_no` → REFUSE**: "the revision chain is linear and
   only moves forward". **This single rule is what keeps the chain linear.**
   Then `transaction.atomic()` + `select_for_update()` on the **parent**: stamp
   `is_approved=True` / `approved_by=request.user` / `approved_at=timezone.now()`
   (`save(update_fields=[...])`); set `document.current_revision_no = revision.revision_no`; **copy**
   `document.extracted_text = revision.extracted_text[:EXTRACT_MAX_CHARS]`; if `document.status == "draft"`
   set `document.status = "active"`;
   `document.save(update_fields=["current_revision_no","extracted_text","status","updated_at"])`;
   `write_audit_log(request.user, document, "revision_approve", {"revision_no": n, "sha256": revision.sha256[:16]})`.
6. **Older approved revisions keep `is_approved=True`** — they *were* approved; rewriting history would be a
   lie. "Only the latest approved version is accessible" is expressed by `current_revision_no` pointing at
   exactly one revision. `ProcurementDocument.current_revision` is the single place that resolves it; templates
   badge that one `badge-green` "Current", every earlier approved one `badge-amber` "Superseded", unapproved
   `badge-muted` "Pending".
7. **The parent's `extracted_text` is a denormalized SEARCH COPY**, refreshed only by (a) approve and
   (b) re-index. The text of record lives on the revision. Say this in **both** docstrings so no later pass
   "fixes" it into a live join.
8. **Delete** (`@require_POST`): allowed **only** when `is_approved is False` **and**
   `revision_no != document.current_revision_no`. Otherwise `messages.error` + redirect — never a 500.
9. `# WARNING:` in `pdocrevision_delete` and `pdocument_delete`: **Django does not remove the file from
   MEDIA_ROOT when the row is deleted.** The confirm text says the record is removed but the stored file is not
   reclaimed here; disk reclamation is a deliberate later job (13.9/13.14), never a silent `os.remove` on a
   path derived from user input.
10. `# WARNING:` on the upload path: validate extension against `ALLOWED_DOC_EXTENSIONS` and size against
    `MAX_UPLOAD_BYTES` **imported explicitly from `apps.core.forms._common` inside the clean method**.
    **Never render an uploaded file inline** (stored-XSS surface) — link to it and let the browser decide.

---

## Model 3 — `ProcurementPolicy` [PPOL-]
`models/DocumentKnowledgeManagement/Policies.py` · base `TenantNumbered` · `NUMBER_PREFIX = "PPOL"`
Bullet **3 Procurement Policy Library**. Modelled on `hrm.HRPolicy` (`apps/hrm/models/ComplianceLegal/Hrpolicy.py:5`).

| Field | Type + args | null/blank | Default | Notes |
|---|---|---|---|---|
| `title` | `CharField(max_length=200)` | — | — | |
| `policy_type` | `CharField(max_length=26, choices=POLICY_TYPE_CHOICES)` | — | `"purchasing_rule"` | 26 fits `supplier_code_of_conduct` (24) |
| `summary` | `CharField(max_length=500, blank=True)` | blank | `""` | |
| `body` | `TextField(blank=True)` | blank | `""` | the rule as written for humans |
| `version_number` | `CharField(max_length=20)` | — | `"1.0"` | |
| `previous_version` | `FK("self", SET_NULL, related_name="superseded_by")` | null+blank | — | supersession chain |
| `status` | `CharField(max_length=12, choices=STATUS_CHOICES)` | — | `"draft"` | **verb-driven, NOT on the form** |
| `effective_from` | `DateField` | null+blank | — | |
| `published_at` | `DateTimeField(editable=False)` | null+blank | — | stamped by the publish verb only |
| `next_review_on` | `DateField` | null+blank | — | |
| `threshold_amount` | `DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])` | null+blank | — | |
| `threshold_basis` | `CharField(max_length=22, choices=THRESHOLD_BASIS_CHOICES, blank=True)` | blank | `""` | 22 fits `annual_supplier_spend` (22) |
| `threshold_currency` | `FK("accounting.Currency", SET_NULL, related_name="procurement_policies")` | null+blank | — | **display label; no conversion, no ledger effect (L29)** |
| `requires_acknowledgment` | `BooleanField(help_text="A hook for 6.17 Policy Management & Acknowledgment - no sign-off ledger is built here.")` | — | `False` | |
| `applies_to` | `FK("core.OrgUnit", SET_NULL, related_name="procurement_policies", help_text="Blank = the whole workspace.")` | null+blank | — | |
| `owner` | `FK(AUTH_USER_MODEL, SET_NULL, related_name="procurement_policies_owned")` | null+blank | — | |
| `document` | `FK("procurement.ProcurementDocument", SET_NULL, related_name="policies", help_text="The policy PDF in the repository - so it inherits revision control and text search.")` | null+blank | — | **this FK makes 6.19 one sub-module, not two halves** |
| `created_by` | `FK(AUTH_USER_MODEL, SET_NULL, editable=False, related_name="+")` | null+blank | — | |

### Choices
```python
POLICY_TYPE_CHOICES = [("purchasing_rule","Purchasing Rule"),("approval_limit","Approval Limit"),
    ("competitive_bidding","Competitive Bidding"),("sole_source","Sole Source"),
    ("supplier_code_of_conduct","Supplier Code of Conduct"),
    ("ethics_conflict","Ethics & Conflict of Interest"),("sustainability","Sustainability"),
    ("data_security","Data Security"),("other","Other")]
STATUS_CHOICES = [("draft","Draft"),("published","Published"),("archived","Archived")]
THRESHOLD_BASIS_CHOICES = [("per_line","Per line"),("per_requisition","Per requisition"),
    ("per_purchase_order","Per purchase order"),("per_contract_year","Per contract year"),
    ("annual_supplier_spend","Annual spend with one supplier")]
STATUS_CSS = {"draft":"badge-muted","published":"badge-green","archived":"badge-slate"}
```

### Meta / behaviour
* `ordering = ["-created_at", "-id"]`
* `unique_together = (("tenant","number"), ("tenant","title","version_number"))` (HRM precedent)
* `indexes`: `("tenant","status")` `prc_ppol_tnt_status_idx`; `("tenant","policy_type")`
  `prc_ppol_tnt_type_idx`; `("tenant","next_review_on")` `prc_ppol_tnt_review_idx`
* `__str__` → `f"{self.title} v{self.version_number}"`
* Properties: `status_css`, `is_review_due` (`next_review_on and next_review_on <= today`)
* `clean()`: cross-tenant `_id` backstop on `applies_to` / `document` / `previous_version`;
  `previous_version` may not be `self`; `threshold_amount` and `threshold_basis` set together or neither
* Module constant `ADVISORY_NOTE` — **ONE constant printed on list, form and detail** so the three surfaces
  cannot disagree: *"A policy records the rule for people to read. It enforces nothing on its own: approval
  routing is decided by the 6.3 Approval Workflow Engine's routing rules, and any threshold here is
  documentation, not a control."*

---

## Model 4 — `KnowledgeResource` [PKR-]
`models/DocumentKnowledgeManagement/KnowledgeResources.py` · base `TenantNumbered` · `NUMBER_PREFIX = "PKR"`
Bullet **4 Best Practices & Templates**, contributes to **5**.

| Field | Type + args | null/blank | Default | Notes |
|---|---|---|---|---|
| `title` | `CharField(max_length=200)` | — | — | |
| `resource_type` | `CharField(max_length=22, choices=RESOURCE_TYPE_CHOICES)` | — | `"guide"` | 22 fits `evaluation_scorecard` (21) |
| `category` | `CharField(max_length=22, choices=CATEGORY_CHOICES)` | — | `"general"` | **a choices field, not an FK — no commodity taxonomy table exists** |
| `audience` | `CharField(max_length=12, choices=AUDIENCE_CHOICES)` | — | `"all"` | |
| `summary` | `CharField(max_length=500, blank=True)` | blank | `""` | |
| `body` | `TextField(blank=True)` | blank | `""` | the guidance itself, rendered on detail |
| `tags` | `CharField(max_length=255, blank=True)` | blank | `""` | + `tag_list` property, same normalization as the document |
| `status` | `CharField(max_length=12, choices=STATUS_CHOICES)` | — | `"draft"` | **verb-driven, NOT on the form** |
| `is_featured` | `BooleanField` | — | `False` | the "start here" shelf |
| `usage_count` | `PositiveIntegerField(editable=False)` | — | `0` | **a click counter, never a derived metric** — say so in the docstring |
| `last_used_at` | `DateTimeField(editable=False)` | null+blank | — | |
| `review_on` | `DateField` | null+blank | — | |
| `owner` | `FK(AUTH_USER_MODEL, SET_NULL, related_name="procurement_knowledge_owned")` | null+blank | — | |
| `document` | `FK("procurement.ProcurementDocument", SET_NULL, related_name="knowledge_resources", help_text="The downloadable artifact in the repository - so it gets revisions and approval like everything else.")` | null+blank | — | |
| `created_by` | `FK(AUTH_USER_MODEL, SET_NULL, editable=False, related_name="+")` | null+blank | — | |

### Choices
```python
RESOURCE_TYPE_CHOICES = [("rfp_template","RFP Template"),("rfq_template","RFQ Template"),
    ("evaluation_scorecard","Bid Evaluation Scorecard"),("negotiation_playbook","Negotiation Playbook"),
    ("checklist","Checklist"),("guide","How-to Guide"),("sample_document","Sample Document"),
    ("training","Training Material")]
CATEGORY_CHOICES = [("general","General"),("it_software","IT & Software"),("facilities","Facilities"),
    ("logistics","Logistics & Freight"),("professional_services","Professional Services"),
    ("raw_materials","Raw Materials"),("capex","Capital Equipment"),("marketing","Marketing"),
    ("other","Other")]
AUDIENCE_CHOICES = [("all","Everyone"),("requester","Requesters"),("buyer","Buyers"),
    ("approver","Approvers"),("legal","Legal")]
STATUS_CHOICES = [("draft","Draft"),("published","Published"),("archived","Archived")]
STATUS_CSS = {"draft":"badge-muted","published":"badge-green","archived":"badge-slate"}
FEATURED_CAP = 6
```

### Meta / behaviour
* `ordering = ["-is_featured", "-created_at", "-id"]` · `unique_together = ("tenant","number")`
* `indexes`: `("tenant","status")` `prc_pkr_tnt_status_idx`; `("tenant","resource_type")`
  `prc_pkr_tnt_type_idx`; `("tenant","is_featured")` `prc_pkr_tnt_feat_idx`
* `__str__` → `f"{self.number or 'PKR'} · {self.title}"`
* `clean()`: normalize `tags`; cross-tenant `_id` backstop on `document`
* Module constant `LIBRARY_NOTE` on list/detail/form: *"Guidance content, not an executable template. The
  requisition templates that actually raise a purchase live in 6.2, the RFx questionnaire builder in 6.6 and the
  pre-approved clause library in 6.8 - this library links to them, it does not replace them."*

---

## Forms — exact `Meta.fields` and exclusions

### `ProcurementDocumentForm(TenantUniqueMixin, TenantModelForm)` — `forms/DocumentKnowledgeManagement/Documents.py`
```python
fields = ["title", "doc_type", "description", "tags", "classification", "owner",
          "supplier_visible", "effective_date", "expires_on", "review_on", "retention_until",
          "supplier", "contract", "purchase_order", "sourcing_event"]
```
**EXCLUDED, each deliberately:** `tenant` (stamped by `TenantUniqueMixin` / `crud_create`), `number`
(`TenantNumbered.save()`), `status` (verb-driven workflow), `current_revision_no` (approve verb only),
`checked_out_by` / `checked_out_at` (lock verbs), `extracted_text` (machine-written, never typed),
`created_by` (authorship stamp), `created_at` / `updated_at` (base timestamps, L22).
`__init__`: `owner.queryset = User.objects.filter(tenant=tenant, is_active=True).order_by("username")`;
`supplier.queryset = Party.objects.filter(tenant=tenant, roles__role__in=("supplier","vendor")).distinct().order_by("name")`;
`contract` / `purchase_order` / `sourcing_event` auto-scoped by `TenantModelForm` (all three carry `tenant`).
`clean()`: `_reject_foreign(self, cleaned, ["supplier", "contract", "purchase_order", "sourcing_event"])`.
`tenant is None` → narrow every one of those to `.none()` and return.

### `ProcurementDocumentRevisionUploadForm` — `forms/DocumentKnowledgeManagement/Revisions.py`
```python
fields = ["file", "change_note"]        # that is the whole form
```
**EXCLUDED:** `tenant`, `document` (comes from the url pk, **never a POST field**), `revision_no`,
`original_filename`, `file_size`, `sha256`, `is_approved`, `approved_by`, `approved_at`, `uploaded_by`,
`extracted_text`, `extraction_note`, `created_at` / `updated_at`.

`clean_file()` — copy `forms/GoodsReceiptInspection/ReceiptDiscrepancies.py:114` / `forms/InvoiceVoucherManagement/SupplierInvoices.py:198` **verbatim in structure**:
```python
def clean_file(self):
    # Imported LOCALLY, never from apps.procurement.forms: CatalogManagement/UploadBatches.py:13
    # defines its own, different MAX_UPLOAD_BYTES (2 MB), and a package-level re-export would make
    # which limit applies depend on import order.
    import os
    from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES
    upload = self.cleaned_data.get("file")
    if upload and hasattr(upload, "name"):
        ext = os.path.splitext(upload.name)[1].lower()
        if ext not in ALLOWED_DOC_EXTENSIONS:
            raise forms.ValidationError(f"File type '{ext}' is not allowed.")
        if getattr(upload, "size", 0) and upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
    return upload
```
**Do not invent a second allow-list. Do not reuse CatalogManagement's 2 MB constant.**

### `ProcurementPolicyForm(TenantUniqueMixin, TenantModelForm)` — `forms/DocumentKnowledgeManagement/Policies.py`
```python
fields = ["title", "policy_type", "summary", "body", "version_number", "previous_version",
          "applies_to", "owner", "document", "effective_from", "next_review_on",
          "threshold_amount", "threshold_basis", "threshold_currency", "requires_acknowledgment"]
```
**EXCLUDED:** `tenant`, `number`, `status` (verb-driven), `published_at` (verb stamp), `created_by`,
`created_at` / `updated_at`.
`__init__`: `previous_version.queryset` = tenant policies **excluding `self.instance.pk`** on edit;
`document.queryset` tenant-scoped (auto by `TenantModelForm`, re-checked by `_reject_foreign`);
`applies_to` auto-scoped; `owner.queryset` = tenant active users;
`threshold_currency.queryset = Currency.objects.filter(is_active=True).order_by("code")` with
`empty_label = "- not labelled -"` (**global table, no tenant column** — the 6.15 `CostForecastForm` note
applies verbatim; `TenantModelForm` leaves it alone).
`clean()`: `_reject_foreign(self, cleaned, ["previous_version", "applies_to", "document"])`.

### `KnowledgeResourceForm(TenantUniqueMixin, TenantModelForm)` — `forms/DocumentKnowledgeManagement/KnowledgeResources.py`
```python
fields = ["title", "resource_type", "category", "audience", "summary", "body", "tags",
          "is_featured", "owner", "document", "review_on"]
```
**EXCLUDED:** `tenant`, `number`, `status` (verb-driven), `usage_count` / `last_used_at` (the Use verb owns
them), `created_by`, `created_at` / `updated_at`.
`clean()`: `_reject_foreign(self, cleaned, ["document"])`.

---

## Views & routes — **every context key is the contract** (L7/L8)

Every list uses `crud_list` and therefore always provides `object_list`, `page_obj`, `q`.
Every detail uses `crud_detail` and therefore provides `obj`.
Every form template reads **only** `form`, `is_edit`, (edit) `obj` and the sub-module note constant —
do **not** invent `page_title` / `submit_label` / `cancel_url` for the `crud_create`/`crud_edit` paths
(the `budgetmapping_create` precedent; 6.15's hand-rolled `costforecast_create` is the exception, and 6.19 has
no hand-rolled create).
Every view `@login_required`; every mutating verb `@require_POST`; privileged verbs also
`@tenant_admin_required`. **Every queryset `filter(tenant=request.tenant)` — never `.all()`.**

### `ProcurementDocument` — `templates/procurement/documentknowledge/document/*.html`

| url path | url name | view function | template | context keys |
|---|---|---|---|---|
| `documents/` | `pdocument_list` | `pdocument_list` | `documentknowledge/document/list.html` | `object_list`, `page_obj`, `q`, `doc_type_choices`, `status_choices`, `classification_choices`, `expiry_choices`, `suppliers`, `owners`, `stats{total,active,expiring,expired,unapproved}`, `search_note` |
| `documents/add/` | `pdocument_create` | `pdocument_create` | `…/document/form.html` | `form`, `is_edit`(False), `search_note` |
| `documents/reindex/` | `pdocument_reindex` | `pdocument_reindex` | — (redirect) | — |
| `documents/run-reminders/` | `pdocument_run_reminders` | `pdocument_run_reminders` | — (redirect) | — |
| `documents/<int:pk>/` | `pdocument_detail` | `pdocument_detail` | `…/document/detail.html` | `obj`, `revisions`, `current_revision`, `policies`, `knowledge_resources`, `can_upload`, `lock_holder`, `search_note` |
| `documents/<int:pk>/edit/` | `pdocument_edit` | `pdocument_edit` | `…/document/form.html` | `form`, `obj`, `is_edit`(True), `search_note` |
| `documents/<int:pk>/delete/` | `pdocument_delete` | `pdocument_delete` | — (redirect) | — |
| `documents/<int:pk>/checkout/` | `pdocument_checkout` | `pdocument_checkout` | — | — |
| `documents/<int:pk>/release/` | `pdocument_release` | `pdocument_release` | — | — |
| `documents/<int:pk>/activate/` | `pdocument_activate` | `pdocument_activate` | — | — |
| `documents/<int:pk>/supersede/` | `pdocument_supersede` | `pdocument_supersede` | — | — |
| `documents/<int:pk>/archive/` | `pdocument_archive` | `pdocument_archive` | — | — |
| `documents/<int:pk>/revisions/add/` | `pdocument_revision_upload` | `pdocument_revision_upload` | `…/revision/form.html` | `form`, `is_edit`(always False), `document`, `upload_note` |

**List assembly** — `_document_qs(request)` pre-narrows **before** `crud_list`:
`?expiry=` allow-listed against `EXPIRY_FILTER_CHOICES` (unknown value → filter skipped, never an empty
register, L11) mapping to `expires_on__lt=today` / `expires_on__range=(today, today+EXPIRY_WARN_DAYS)` /
`review_on__lte=today` / `retention_until__lt=today`; `?tag=` → `tags__icontains` (stripped, ignored when blank).
Then:
```python
crud_list(request, _document_qs(request), TEMPLATE_LIST,
    search_fields=("number","title","description","tags","extracted_text"),
    filters=(("doc_type","doc_type",False), ("status","status",False),
             ("classification","classification",False), ("supplier","supplier_id",True),
             ("owner","owner_id",True)),
    extra_context={...})
```
`select_related("supplier","owner","contract","purchase_order","sourcing_event")`.
`stats` = **ONE** `aggregate` with `Count("pk", filter=Q(...))`, never five COUNTs.
`suppliers` = tenant Party, supplier/vendor role, `.distinct().order_by("name")`; `owners` = tenant active
users `.order_by("username")`; both `.none()` when `request.tenant is None`.

`SEARCH_NOTE` (module-level, shared list + detail): *"Search matches the title, description, tags and any text
read from the approved file. Text is read from PDFs that carry a text layer and from plain-text uploads; a
scanned image has no text to read."*

**Verbs** — all `@require_POST`, all `write_audit_log`, all redirect to `procurement:pdocument_detail`:

| verb | rule |
|---|---|
| `pdocument_checkout` | refuse when already held by another user, naming the holder; stamp `checked_out_by=request.user`, `checked_out_at=timezone.now()` |
| `pdocument_release` | holder **or** tenant admin (force release); clears both lock columns |
| `pdocument_activate` | `draft` / `superseded` / `archived` → `active` |
| `pdocument_supersede` | `active` → `superseded` (refuse otherwise) |
| `pdocument_archive` | any → `archived` |
| `pdocument_reindex` | `@tenant_admin_required`; re-runs `extract_document_text` over ≤ `REINDEX_ROW_CAP` documents whose `extracted_text` is empty **and** which have a current approved revision; `messages.success` with `{"indexed": n, "skipped": n}`; ONE audit row; **redirect to the LIST** |
| `pdocument_run_reminders` | `run_document_reminders_audited`; `messages.success` with raised/skipped; **redirect to the LIST** |

Each rejects a disallowed transition with `messages.error` + redirect — never a 500, never a silent no-op.

### `ProcurementDocumentRevision` — `templates/procurement/documentknowledge/revision/*.html`

| url path | url name | view function | template | context keys |
|---|---|---|---|---|
| `document-revisions/` | `pdocrevision_list` | `pdocrevision_list` | `…/revision/list.html` | `object_list`, `page_obj`, `q`, `documents`, `approval_choices`, `stats{total,approved,pending}`, `revision_note` |
| `document-revisions/<int:pk>/` | `pdocrevision_detail` | `pdocrevision_detail` | `…/revision/detail.html` | `obj`, `document`, `is_current`, `revision_note` |
| `document-revisions/<int:pk>/approve/` | `pdocrevision_approve` | `pdocrevision_approve` | — | `@tenant_admin_required` + `@require_POST`; rules 5 above |
| `document-revisions/<int:pk>/delete/` | `pdocrevision_delete` | `pdocrevision_delete` | — | `@require_POST`; rule 8 above |

`pdocrevision_list` is **the "Version Control" sidebar bullet's landing page** — every revision in the
workspace, newest first.
```python
crud_list(request, _revision_qs(request), TEMPLATE_LIST,
    search_fields=("document__number","document__title","change_note","sha256"),
    filters=(("document","document_id",True), ("approved","is_approved",False)),
    extra_context={...})
```
`select_related("document","uploaded_by","approved_by")`.
`approval_choices = [("True","Approved"), ("False","Pending approval")]` — **exactly the strings `crud_list`
maps to booleans**; any other value raises inside `.filter()` and is skipped.

`REVISION_NOTE`: *"A revision is immutable. Approving one makes it the document's current version; earlier
approved revisions stay on the record as superseded. There is no edit."*
`UPLOAD_NOTE`: the allowed extensions (rendered **from `ALLOWED_DOC_EXTENSIONS`**, not hard-coded twice), the
20 MB cap, and the honest line about text extraction. **Never the word "OCR".**

**No `pdocrevision_edit`** — documented exemption in the url module docstring.

### `ProcurementPolicy` — `templates/procurement/documentknowledge/policy/*.html`

| url path | url name | view function | template | context keys |
|---|---|---|---|---|
| `procurement-policies/` | `ppolicy_list` | `ppolicy_list` | `…/policy/list.html` | `object_list`, `page_obj`, `q`, `policy_type_choices`, `status_choices`, `org_units`, `review_choices`, `stats{total,published,draft,review_due}`, `advisory_note` |
| `procurement-policies/add/` | `ppolicy_create` | `ppolicy_create` | `…/policy/form.html` | `form`, `is_edit`(False), `advisory_note` |
| `procurement-policies/<int:pk>/` | `ppolicy_detail` | `ppolicy_detail` | `…/policy/detail.html` | `obj`, `advisory_note`, `supersedes`, `superseded_by_rows`, `is_review_due` |
| `procurement-policies/<int:pk>/edit/` | `ppolicy_edit` | `ppolicy_edit` | `…/policy/form.html` | `form`, `obj`, `is_edit`(True), `advisory_note` |
| `procurement-policies/<int:pk>/delete/` | `ppolicy_delete` | `ppolicy_delete` | — | `@require_POST` |
| `procurement-policies/<int:pk>/publish/` | `ppolicy_publish` | `ppolicy_publish` | — | `@tenant_admin_required` + `@require_POST` |
| `procurement-policies/<int:pk>/archive/` | `ppolicy_archive` | `ppolicy_archive` | — | `@require_POST` |

```python
crud_list(request, _policy_qs(request), TEMPLATE_LIST,
    search_fields=("number","title","summary","body"),
    filters=(("policy_type","policy_type",False), ("status","status",False),
             ("org_unit","applies_to_id",True)),
    extra_context={...})
```
`select_related("applies_to","owner","document","threshold_currency")`.
`?review=due` pre-narrow (`next_review_on__lte=today`) applied in `_policy_qs` **before** `crud_list`.
`review_choices = [("due","Review overdue")]`. `supersedes` = `obj.previous_version`;
`superseded_by_rows` = `obj.superseded_by.all()[:10]`.

`ppolicy_publish`: `draft` → `published`, stamps `published_at = timezone.now()`,
`write_audit_log(user, obj, "policy_publish", {...})`. Already published → idempotent `messages.info`.
Archived → refuse. `ppolicy_archive`: any → `archived`, audit `policy_archive`.

### `KnowledgeResource` — `templates/procurement/documentknowledge/knowledgeresource/*.html`

| url path | url name | view function | template | context keys |
|---|---|---|---|---|
| `knowledge/` | `knowledgeresource_list` | `knowledgeresource_list` | `…/knowledgeresource/list.html` | `object_list`, `page_obj`, `q`, `resource_type_choices`, `category_choices`, `audience_choices`, `status_choices`, `featured_choices`, `featured`, `stats{total,published,featured,used}`, `library_note` |
| `knowledge/add/` | `knowledgeresource_create` | `knowledgeresource_create` | `…/form.html` | `form`, `is_edit`(False), `library_note` |
| `knowledge/<int:pk>/` | `knowledgeresource_detail` | `knowledgeresource_detail` | `…/detail.html` | `obj`, `library_note`, `document`, `is_review_due` |
| `knowledge/<int:pk>/edit/` | `knowledgeresource_edit` | `knowledgeresource_edit` | `…/form.html` | `form`, `obj`, `is_edit`(True), `library_note` |
| `knowledge/<int:pk>/delete/` | `knowledgeresource_delete` | `knowledgeresource_delete` | — | `@require_POST` |
| `knowledge/<int:pk>/publish/` | `knowledgeresource_publish` | `knowledgeresource_publish` | — | `@require_POST` |
| `knowledge/<int:pk>/archive/` | `knowledgeresource_archive` | `knowledgeresource_archive` | — | `@require_POST` |
| `knowledge/<int:pk>/use/` | `knowledgeresource_use` | `knowledgeresource_use` | — | `@login_required` + `@require_POST` |

```python
crud_list(request, _resource_qs(request), TEMPLATE_LIST,
    search_fields=("number","title","summary","body","tags"),
    filters=(("resource_type","resource_type",False), ("category","category",False),
             ("audience","audience",False), ("status","status",False),
             ("featured","is_featured",False)),
    extra_context={...})
```
`select_related("owner","document")`. `featured_choices = [("True","Featured only"),("False","Not featured")]`.
`featured` = the "start here" shelf — `status="published", is_featured=True`, capped at `FEATURED_CAP`,
computed separately and **not** paginated.

`knowledgeresource_use`: refuse on `archived`; otherwise `usage_count = F("usage_count") + 1`,
`last_used_at = timezone.now()`, `save(update_fields=["usage_count","last_used_at","updated_at"])`,
`refresh_from_db(fields=["usage_count"])`,
`write_audit_log(user, obj, "knowledge_resource_used", {"usage_count": obj.usage_count})`, then **redirect back
to the resource detail page**.
`# WARNING:` never redirect to a FileField URL from a verb — an unvalidated redirect target derived from stored
data is an open-redirect hop; the detail page is one extra click that removes the surface.

### URL module rules
* Four NEW first segments, **verified free** against the whole concatenated inventory:
  **`documents/`**, **`document-revisions/`**, **`procurement-policies/`**, **`knowledge/`**.
  (`templates/` is 6.2's — that is why the library is `knowledge/`. `contracts/`, `clauses/`, `milestones/`,
  `renewals/` are 6.8's.) This app registers **no** greedy `<str:…>` converter, so there is no cross-module
  shadowing surface.
* **Literals before `<int:pk>`** in every module — Django is first-match-wins. `documents/reindex/` and
  `documents/run-reminders/` MUST precede `documents/<int:pk>/`.
* `urls/DocumentKnowledgeManagement/__init__.py` concatenates in the order
  **Documents → Revisions → Policies → KnowledgeResources**, with the segment-inventory docstring.

**Current inventory (dumped from `path()` calls, authoritative — the `urls/__init__.py` docstring is stale):**
`<root "">, activity, alerts, amendments, analytics, approvals, asn, awards, backorders,
budget-availability, budget-mappings, budget-variance, capture, catalog-items, catalog-tiers,
catalog-uploads, clauses, commitments, contract-amendments, contract-sign, contracts, cost-forecasts,
delegations, delivery-confirmation, delivery-schedules, eauc, escalations, events, inbound-tracking,
invoice-disputes, invoice-vouchers, match-board, match-variances, maverick-findings, milestones,
payment-schedule, po-changes, po-generation, po-tracking, portal-access, punchout, quick-requisition,
receipt-audit, receipt-discrepancies, receipt-tolerances, receiving-console, renewals, reports,
requisitions, returns-to-vendor, rfx, spend, spend-report-snapshots, spend-reports, spend-rules,
submissions, supplier-invoice-lines, supplier-invoices, suspensions, templates, tolerance-exceptions,
vendor-portal`

**Known forward reference:** `document/detail.html` links `procurement:pdocrevision_*` (step 2) and
`revision/detail.html` links `procurement:pdocument_detail` (step 1). Neither renders until both url modules
exist; `manage.py check` at Integrate is the first point both are present. **Expected — do not "fix" it by
inlining a hard-coded path.**

**Cross-module links on `document/detail.html`** (verified url names):
`scm:contract_detail` · `scm:purchaseorder_detail` · **`procurement:event_detail`** (NOT
`sourcingevent_detail`) · `core:party_detail` for the supplier. Render "—" when the FK is unset.

---

## Badge / status → theme class map

Colour-named classes only. `badge-success` / `badge-warning` / `badge-danger` **do not exist** in
`static/css/theme.css` and render unstyled (L33). Every badge carries a
`{{ obj.get_<field>_display }}` label and an `{% else %}` fallback of `badge-slate`.

| Model.field | value | class |
|---|---|---|
| `ProcurementDocument.status` | `draft` | `badge-muted` |
| | `active` | `badge-green` |
| | `superseded` | `badge-amber` |
| | `archived` | `badge-slate` |
| `ProcurementDocument.classification` | `public` | `badge-info` |
| | `internal` | `badge-slate` |
| | `confidential` | `badge-amber` |
| | `restricted` | `badge-red` |
| `ProcurementDocument` expiry state | expired (`is_expired`) | `badge-red` |
| | expiring ≤ 30d (`is_expiring`) | `badge-amber` |
| | otherwise / no date | `badge-muted` |
| `ProcurementDocumentRevision` chain state | current (`is_current`) — "Current" | `badge-green` |
| | approved but older — "Superseded" | `badge-amber` |
| | `is_approved is False` — "Pending" | `badge-muted` |
| `ProcurementPolicy.status` | `draft` | `badge-muted` |
| | `published` | `badge-green` |
| | `archived` | `badge-slate` |
| `ProcurementPolicy.is_review_due` | True — "Review overdue" | `badge-red` |
| `KnowledgeResource.status` | `draft` | `badge-muted` |
| | `published` | `badge-green` |
| | `archived` | `badge-slate` |
| `KnowledgeResource.is_featured` | True — "Featured" | `badge-info` |

Available (do not use anything else): `badge-green badge-red badge-amber badge-info badge-muted badge-slate`
(+ `badge-group` as a wrapper). Layout: `stat-grid stat-card stat-icon filter-bar page-header`.
Text: `text-muted text-danger text-ok text-warn text-red text-brand text-right`.

---

## Wire-up (Integrate phase ONLY — single writer, surgical `Edit`, **never** `Write`)

### `apps/procurement/models/__init__.py` — append, and add every name to `__all__`
```python
from .DocumentKnowledgeManagement.Documents import (
    ProcurementDocument,
    expiring_documents,
    run_document_reminders,
    run_document_reminders_audited,
)
from .DocumentKnowledgeManagement.Revisions import (
    ProcurementDocumentRevision,
    extract_document_text,
)
from .DocumentKnowledgeManagement.Policies import ProcurementPolicy
from .DocumentKnowledgeManagement.KnowledgeResources import KnowledgeResource
```
`EXTRACT_MAX_CHARS`, `file_sha256` and the `*_CHOICES` tuples are deliberately **not** hoisted — reachable as
`ProcurementDocument.DOC_TYPE_CHOICES` etc. (the 6.14/6.15 rule).

### `apps/procurement/forms/__init__.py`
```python
from .DocumentKnowledgeManagement.Documents import ProcurementDocumentForm
from .DocumentKnowledgeManagement.Revisions import ProcurementDocumentRevisionUploadForm
from .DocumentKnowledgeManagement.Policies import ProcurementPolicyForm
from .DocumentKnowledgeManagement.KnowledgeResources import KnowledgeResourceForm
```
(The existing "`MAX_UPLOAD_BYTES` is NOT re-exported" note covers this sub-module too.)

### `apps/procurement/views/__init__.py` — **all 30 view names** (a missing one is an `AttributeError` at URLconf import, not a 404)
```python
from .DocumentKnowledgeManagement.Documents import (
    pdocument_list, pdocument_create, pdocument_detail, pdocument_edit, pdocument_delete,
    pdocument_checkout, pdocument_release, pdocument_activate, pdocument_supersede,
    pdocument_archive, pdocument_reindex, pdocument_run_reminders,
)
from .DocumentKnowledgeManagement.Revisions import (
    pdocrevision_list, pdocrevision_detail, pdocument_revision_upload,
    pdocrevision_approve, pdocrevision_delete,
)
from .DocumentKnowledgeManagement.Policies import (
    ppolicy_list, ppolicy_create, ppolicy_detail, ppolicy_edit, ppolicy_delete,
    ppolicy_publish, ppolicy_archive,
)
from .DocumentKnowledgeManagement.KnowledgeResources import (
    knowledgeresource_list, knowledgeresource_create, knowledgeresource_detail,
    knowledgeresource_edit, knowledgeresource_delete, knowledgeresource_publish,
    knowledgeresource_archive, knowledgeresource_use,
)
```
(12 + 5 + 7 + 8 = **32** — the plan said "30"; the list above is authoritative.)

### `apps/procurement/urls/__init__.py`
`from .DocumentKnowledgeManagement import urlpatterns as _dkm_documentknowledge`, spliced **LAST** in
`urlpatterns` (the 6.13/6.14/6.15 belt-and-braces posture). Add the four new first segments to the module
docstring's inventory.

### `apps/procurement/admin.py` — `@admin.register` for all four
* `ProcurementDocumentAdmin` — `list_display` number/title/doc_type/status/classification/supplier/expires_on/
  current_revision_no; `list_filter` tenant/status/doc_type/classification; `search_fields` number/title/tags;
  `readonly_fields` number/current_revision_no/extracted_text/checked_out_by/checked_out_at/created_by/
  created_at/updated_at; `raw_id_fields` supplier/contract/purchase_order/sourcing_event/owner/created_by
* `ProcurementDocumentRevisionAdmin` — **everything readonly except `change_note`**; `raw_id_fields` document
* `ProcurementPolicyAdmin` — `readonly_fields` number/published_at/created_by/created_at/updated_at;
  `raw_id_fields` previous_version/applies_to/owner/document/threshold_currency/created_by
* `KnowledgeResourceAdmin` — `readonly_fields` number/usage_count/last_used_at/created_by/created_at/updated_at;
  `raw_id_fields` owner/document/created_by

### `apps/core/navigation.py` — exactly ONE new block, inserted after the `"6.15"` block
```python
"6.19": {
    "Central Document Repository":  "procurement:pdocument_list",
    "Version Control":              "procurement:pdocrevision_list",
    "Procurement Policy Library":   "procurement:ppolicy_list",
    "Best Practices & Templates":   "procurement:knowledgeresource_list",
    "Full-Text Search & Indexing":  "procurement:pdocument_list#search",
},
```
`_safe_reverse` fragment support **VERIFIED** (`navigation.py:1838`, `_route_name` above it; precedent
`procurement:invoicevoucher_dashboard#discount` at `:1605`). **The register's filter-bar card must therefore
carry `id="search"`** (with `scroll-margin-top`, the 6.13 idiom). **No sidebar key for the upload page or any
verb** — this dict maps NavERP.md bullets to pages.

### Seeder — `apps/procurement/management/commands/seed_procurement.py`
* Add `_seed_document_knowledge(self, tenant)`; call it **LAST** in `handle()`'s per-tenant block, **after
  `self._seed_budget_cost(tenant)`** (line ~262) — its documents link to the suppliers, contracts, orders and
  sourcing events every block above has created.
* Extend the module docstring and `Command.help` with the 6.19 line.
* Extend the `--flush` block, children first: `ProcurementDocumentRevision` → `KnowledgeResource` →
  `ProcurementPolicy` → `ProcurementDocument`. (The two `document` FKs are `SET_NULL`, so order is not
  load-bearing; children-first keeps the flush reading top-down like every block above.)
* Add the four models + `extract_document_text` to the `from apps.procurement.models import (...)` block.
* **Reuse only** — create no Party, contract, PO, sourcing event, OrgUnit or Currency: first supplier `Party`
  (via `PartyRole`), first `scm.SupplierContract`, first `scm.PurchaseOrder`, first
  `procurement.SourcingEvent`, first non-root `OrgUnit`, first active `Currency`, workspace members. Skip with a
  `self.style.WARNING` line when no supplier Party exists (the SMOKETEST-tenant posture).
* **Idempotent, per block:** `if ProcurementDocument.objects.filter(tenant=tenant).exists(): … skipping`, and
  separately for policies and knowledge resources. Numbered models use the existence guard, never a bare
  `.create()` in a loop that could re-mint numbers.
* **Documents (4):** an **active warranty** (supplier + purchase_order, `expires_on = today + 45d`); an
  **expired certificate of insurance** (supplier + contract, `expires_on = today - 20d`) so the Expired filter
  and the reminder scan have an honest row; a **draft specification** (sourcing_event, no revision →
  `current_revision_no = 0`) so the "no revision yet" empty state is real; an **archived correspondence pack**
  with `retention_until = today - 10d` so the Past-retention filter has a row.
* **Revisions:** 2 each on the two live documents, minted through `ContentFile` with a small **`.txt`** payload
  (a plain-text extension the extractor genuinely reads, so `extracted_text` is really populated and search is
  demonstrably working **without shipping a binary PDF**). r1 approved then superseded by an approved r2; the
  parent's `current_revision_no` and `extracted_text` set through the same code path the approve verb uses.
  `# WARNING:` the seeder writes real files under MEDIA_ROOT — deterministic filenames plus the `exists()`
  guard, so a second run cannot pile up `_XXXX`-suffixed duplicates.
* **Policies (3):** a **published** competitive-bidding rule (`threshold_amount=10000`,
  `threshold_basis="per_requisition"`, currency, `applies_to` a department, `published_at` stamped) whose
  `previous_version` is an **archived** v1.0 row; plus a **draft** sole-source policy with `next_review_on` in
  the past so the Review-overdue filter has a row.
* **Knowledge resources (4):** a **featured published RFP template** linked to a seeded `ProcurementDocument`;
  a bid-evaluation scorecard; a negotiation playbook with `usage_count=7` + `last_used_at`; a draft checklist.
* Print the usual per-tenant `SUCCESS` counts.

### No `config/settings.py` / `config/urls.py` change
`apps/procurement` is long since installed and included. This is an **EXTEND** run.

---

## Concurrency & house rules

* **The migration slot is NOT pre-reserved.** The leaf on disk at contract time is
  `0025_remove_budgetmapping_prc_bmap_tnt_active_idx_and_more.py`, but the 6.16 plan reserves `0026` and the
  6.19 plan says `0026` — a direct contradiction, and peer sessions may land 6.16/6.17/6.18 first.
  **At Integrate: `ls apps/procurement/migrations/`, read the real leaf, agree the next free number with any
  concurrent session (L43), then `makemigrations procurement`.** Review the generated file before committing:
  it must contain **four tables and nine indexes and nothing else** — if it also wants to alter a table this
  pass did not touch, **STOP** (another session's model edit leaked in). Then
  `makemigrations --check --dry-run` → "No changes detected".
* **Shared files are surgical `Edit` only, never `Write`:** the four package `__init__.py` files, `admin.py`,
  `seed_procurement.py`, `apps/core/navigation.py`, `apps/procurement/urls/__init__.py`,
  `apps/procurement/tests/conftest.py`. Another session may be building a different sub-module in this same
  checkout (L43).
* **Never `seed_procurement --flush`** — it wipes every peer session's demo data. Run `seed_procurement` plain,
  **twice**, and assert the second run prints "already present, skipping" for all three 6.19 blocks and creates
  no duplicate files under MEDIA_ROOT.
* **Hands off other sessions' files.** `apps/procurement/tests/test_budgetcost_*.py` (four untracked files) are
  another session's (L45) — never `git add` them.
* **One file per commit**, PowerShell-safe (`;`, never `&&`). **Never `git push`.**
* Build order is **serial**: for each entity, its four backend files then its three templates, finished
  completely before the next entity starts. Do not touch shared files during Build — they all wait for Integrate.
* Not-yet-wired siblings of THIS sub-module are imported **from their entity module**
  (`from apps.procurement.models.DocumentKnowledgeManagement.Documents import ProcurementDocument`), never from
  `apps.procurement.models` — a package-level re-export would be a star-import cycle at URLconf import time.
* Smoke expectations worth pinning: every verb on **GET → 405**; a non-admin tenant user on
  `pdocrevision_approve` / `pdocument_reindex` / `ppolicy_publish` → **403** (`PermissionDenied`, not a
  redirect); cross-tenant pk on every `<int:pk>` route → **404**; junk params (`?status=nope`, `?supplier=abc`,
  `?supplier=0`, `?supplier=999999999999999999999`, `?expiry=zzz`, `?approved=maybe`, `?page=9999`) → 200 and
  **still shows rows** (L11); no `{#` / `{% comment` leak in any rendered body.
