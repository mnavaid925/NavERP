# FROZEN BUILD CONTRACT — Procurement 6.13 Invoice & Voucher Management (migration 0020)

Builders implement **ONE entity stack each** (model + form + views + urls + templates) and **NOTHING else**.
Shared files (`models/__init__.py`, `forms/__init__.py`, `views/__init__.py`, `urls/__init__.py`, `admin.py`,
`seed_procurement.py`, `apps/core/navigation.py`, `apps/procurement/views/_helpers.py`, migrations) belong to
the solo **Integrator**. No git, no `makemigrations`, no `migrate`, no DB writes by builders.

Imports are **ABSOLUTE** everywhere. Cross-entity references import the entity **MODULE** directly:
`from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice`
— NEVER `from apps.procurement.models import SupplierInvoice` (the sub-package is not wired until the
Integrator lands it, and a star-import cycle will 500 at URLconf import). Inside a model module, every
cross-app FK is a **STRING** (`"scm.PurchaseOrder"`), never an import.

Lane → entity assignment (four parallel builders, one lane each):

| Lane | Model | Prefix | URL segment | Owns (standalone pages) |
|---|---|---|---|---|
| **A** | `SupplierInvoice` | `SIV` | `supplier-invoices/` | `capture/`, `duplicates/`, `invoice-vouchers/` (dashboard) |
| **B** | `SupplierInvoiceLine` | — | `supplier-invoice-lines/` | `payment-schedule/` |
| **C** | `InvoiceMatchVariance` | — | `match-variances/` | `match-board/` |
| **D** | `InvoiceDispute` | `DSP` | `invoice-disputes/` | `dispute-aging/` |

**Merge order:** B, C, D first; **A LAST** — the dashboard and the capture flow import the other three
entity modules by absolute path.

## Shared toolkit (VERIFIED by reading the files — not copied from 6.9)

`from apps.procurement.models._base import *` gives: `TenantOwned`, `TenantNumbered` (`NUMBER_PREFIX`,
auto `number` assigned in `save()` with a 5-attempt IntegrityError retry — you still declare
`unique_together` in your own `Meta`), `ZERO` (=`Decimal("0")`), `MAX_Q2` (=`Decimal("9999999999.99")`),
`q2(value)` (quantize 2dp **and clamp to ±MAX_Q2**), `next_number`, `ValidationError`,
`MinValueValidator`, `MaxValueValidator`, `IntegrityError`, `models`, `transaction`, `F`, `Q`, `Sum`,
`timezone`, `settings`, `secrets`, `Decimal`.
**NOT exported:** `Count`, `Prefetch`, `timedelta`, `inlineformset_factory`. Import them yourself.

`from apps.procurement.forms._common import *` gives: `forms`, `ValidationError`,
`inlineformset_factory`, `TenantModelForm`, `TenantUniqueMixin`, `_reject_foreign(form, cleaned, names)`.
`TenantModelForm` (`apps/core/forms/_common.py:25`) takes `tenant=` as a kwarg, auto-applies
`form-input` / `form-select` / `form-textarea` / `type=date` widgets, and auto-scopes every
`ModelChoiceField` **whose target model has a `tenant` column**. `TenantUniqueMixin` mixes in **FIRST**
stamps `instance.tenant` before `full_clean()`.

`from apps.procurement.views._common import *` gives: `messages`, `login_required`,
`get_object_or_404`, `redirect`, `render`, `timezone`, `require_POST`, `crud_create`, `crud_delete`,
`crud_detail`, `crud_edit`, `crud_list`, `tenant_admin_required`, `write_audit_log`.
**NOT exported:** `Count`, `Q`, `transaction`, `reverse`, `Decimal`, `timedelta`, `Paginator`. Import them.

`apps/procurement/views/_helpers.py` — **DO NOT star-import it.** It exports 6.2's
`DUPLICATE_WINDOW_DAYS = 30`, which would collide with 6.13's own `DUPLICATE_WINDOW_DAYS = 90`. Nothing
in 6.13 needs it. Do not touch `PROCUREMENT_CONTENT_MODELS`.

`apps/core/crud.py` (verified signatures → context keys):
- `crud_list(request, qs, template, *, search_fields=(), filters=(), extra_context=None, per_page=15)`
  → ctx `object_list`, `page_obj`, `q`. `filters` = `[(get_param, orm_lookup, is_int)]`; int filters go
  through `as_db_int` (junk/over-range silently skips the filter, never 500s); `"True"`/`"False"` strings
  map to booleans. All filtering happens BEFORE pagination.
- `crud_detail(request, *, model, pk, template, extra_context=None, select_related=())` → ctx `obj`.
- `crud_create(request, *, form_class, template, success_url, extra_context=None, set_tenant=True,
  audit=True)` → ctx `form`, `is_edit=False`.
- `crud_edit(request, *, model, pk, form_class, template, success_url, extra_context=None, audit=True)`
  → ctx `form`, `obj`, `is_edit=True`.
- `crud_delete(request, *, model, pk, success_url, audit=True)` → redirects (no confirm template).
- `paginate(request, qs, per_page=15)` → a page with `.window` — use it for hand-rolled pages.
- `write_audit_log(user, obj, action, changes=None, tenant=None)`.

**FK scoping (verified):** `accounting.Currency` is **GLOBAL** (no `tenant` column) — leave unscoped and
NEVER pass it to `_reject_foreign`. `scm.PurchaseOrderLine` and `scm.GoodsReceiptLine` are plain
`models.Model` with **NO tenant column** — `TenantModelForm` cannot scope them, `_reject_foreign` cannot
check them; narrow them through the header (`purchase_order__tenant=` / `goods_receipt__tenant=`) in
`__init__` AND re-check in `clean()`. Everything else (`core.Party`, `core.Document`, `scm.Item`,
`scm.PurchaseOrder`, `scm.GoodsReceiptNote`, `accounting.Bill`, `accounting.JournalEntry`,
`accounting.PaymentTerm`, `accounting.TaxCode`, `accounting.GLAccount`,
`procurement.VendorInvoiceSubmission`) is tenant-scoped.

## Spine verification (all 14 — every one EXISTS)

| Entity | file:line |
|---|---|
| `scm.PurchaseOrder` | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:15` |
| `scm.PurchaseOrderLine` | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:172` |
| `scm.GoodsReceiptNote` | `apps/scm/models/ProcurementManagement/GoodsReceiptNotes.py:15` |
| `scm.GoodsReceiptLine` | `apps/scm/models/ProcurementManagement/GoodsReceiptNotes.py:166` |
| `scm.Item` | `apps/scm/models/InventoryManagement/Items.py:73` |
| `core.Party` | `apps/core/models/Party.py:5` (has `tenant`) |
| `core.Document` | `apps/core/models/Document.py:5` (has `tenant`) |
| `accounting.Bill` | `apps/accounting/models/AccountsPayable/Bills.py:6` |
| `accounting.PaymentTerm` | `apps/accounting/models/AccountsPayable/PaymentTerms.py:6` |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` (GLOBAL) |
| `accounting.TaxCode` | `apps/accounting/models/Tax/TaxCodes.py:6` |
| `accounting.GLAccount` | `apps/accounting/models/GeneralLedger/GLAccounts.py:5` |
| `accounting.JournalEntry` | `apps/accounting/models/GeneralLedger/JournalEntries.py:5` |
| `procurement.VendorInvoiceSubmission` | `apps/procurement/models/VendorManagement/VendorInvoiceSubmissions.py:16` |

Ledger shapes you must code against: `Bill` has **`party`** (not `vendor`) and **`payment_terms`**
(plural); `bill_date` is **required**; `subtotal`/`tax_total`/`total` are `editable=False` and
`recalc_totals()` fills them from `BillLine` rows. `JournalEntry` has `entry_type`
(`"invoice"`/`"reversal"` exist), `status` (`draft`/`pending_approval`/`posted`/`void`), `entry_date`
(required), `description`, `reference`, `reversal_of`, `created_by`. `JournalLine.gl_account` is
`PROTECT` and **NOT nullable** — see the GL-resolution rule below.
`scm.GoodsReceiptNote` has `vendor` only via `purchase_order.vendor`; `STATUS_CHOICES = draft/received/cancelled`.
`scm.PurchaseOrderLine.receipt_lines` is the reverse of `GoodsReceiptLine.po_line`.

## URL first segments — collision-checked

Every first segment already in the concatenated `urls/__init__.py` (verified by grep, 45 of them):
activity, alerts, amendments, analytics, approvals, asn, awards, backorders, bids, catalog-items,
catalog-tiers, catalog-uploads, clauses, contract-amendments, contract-sign, contracts, delegations,
delivery-confirmation, delivery-schedules, eauc, escalations, events, inbound-tracking, milestones,
po-changes, po-generation, po-tracking, portal-access, punchout, quick-requisition, receipt-audit,
receipt-discrepancies, receipt-tolerances, receiving-console, renewals, reports, requisitions,
returns-to-vendor, rfx, submissions, suspensions, templates, tolerance-exceptions, vendor-portal, `""`.

**Assigned and FREE:** `supplier-invoices/`, `supplier-invoice-lines/`, `match-variances/`,
`invoice-disputes/`, `capture/`, `duplicates/`, `match-board/`, `payment-schedule/`,
`discount-opportunities/`, `dispute-aging/`, `invoice-vouchers/`. No collisions. There is no greedy
`<str:…>` route anywhere in the app, so nothing can shadow these.

## related_name collision check (verified free)

`procurement_supplier_invoices` (on `core.Party`, `scm.PurchaseOrder`, `scm.GoodsReceiptNote`,
`accounting.Bill`, `accounting.PaymentTerm`, `accounting.TaxCode`, `core.Document`,
`procurement.VendorInvoiceSubmission`) — free; the closest existing name is
`procurement_invoice_submissions` (6.4, `VendorInvoiceSubmissions.py:30,34`).
`procurement_invoice_lines` (on `scm.PurchaseOrderLine`, `scm.GoodsReceiptLine`, `scm.Item`,
`accounting.GLAccount`, `accounting.TaxCode`) — free. `procurement_invoice_disputes` (on `core.Party`)
— free. `lines` / `variances` / `disputes` / `resolved_disputes` / `duplicates` — free within
`procurement`. **`accounting.Currency` needs a related_name too** — use `procurement_supplier_invoices`
(also free there).

---

# LANE A — SupplierInvoice [`SIV-`]

Files: `apps/procurement/{models,forms,views,urls}/InvoiceVoucherManagement/SupplierInvoices.py`
+ `templates/procurement/invoicevouchermanagement/supplierinvoice/{list,detail,form}.html`
+ `templates/procurement/invoicevouchermanagement/{capture,duplicates,dashboard}.html`

## MODEL `SupplierInvoice(TenantNumbered)`, `NUMBER_PREFIX = "SIV"`

CHOICES — copy **verbatim**, exact string values (template badges compare against them):
```python
STATUS_CHOICES = [("draft","Draft"),("parked","Parked"),("captured","Captured"),("blocked","Blocked"),
    ("disputed","Disputed"),("pending_approval","Pending Approval"),("approved","Approved"),
    ("scheduled","Scheduled"),("paid","Paid"),("void","Void"),("reversed","Reversed")]
INVOICE_TYPE_CHOICES = [("standard","Standard Invoice"),("credit_memo","Credit Memo"),
    ("debit_memo","Debit Memo"),("prepayment","Prepayment / Down-payment Request"),
    ("service","Service Invoice (PO-less)")]
MATCH_BASIS_CHOICES = [("quantity","Quantity"),("amount","Amount"),("none","No Match")]
MATCH_STATUS_CHOICES = [("not_run","Not Run"),("matched","Matched"),
    ("within_tolerance","Matched Within Tolerance"),("price_variance","Price Variance"),
    ("quantity_variance","Quantity Variance"),("total_variance","Total Amount Variance"),
    ("fx_variance","FX / Conversion-Rate Variance"),("no_receipt","No Receipt Posted"),
    ("over_invoiced","Over-Invoiced"),("duplicate_suspect","Duplicate Suspect")]
SOURCE_CHOICES = [("manual","Manual Keying"),("pdf_text_layer","PDF Text-Layer Extraction"),
    ("e_invoice_xml","Structured E-Invoice (XML)"),("vis","Vendor Portal Submission"),("ocr","OCR Engine")]
DISCOUNT_BASE_CHOICES = [("net_of_tax","Net of Tax"),("gross","Gross (Incl. Tax)")]
```

Fields (order matters — it is the form/`<dl>` render order):
`vendor` FK `"core.Party"` PROTECT `related_name="procurement_supplier_invoices"`;
`purchase_order` FK `"scm.PurchaseOrder"` SET_NULL null blank same related_name;
`goods_receipt` FK `"scm.GoodsReceiptNote"` SET_NULL null blank same;
`bill` FK `"accounting.Bill"` SET_NULL null blank **editable=False** same;
`journal_entry` FK `"accounting.JournalEntry"` SET_NULL null blank **editable=False** same;
`payment_term` FK `"accounting.PaymentTerm"` SET_NULL null blank same;
`currency` FK `"accounting.Currency"` SET_NULL null blank same (**GLOBAL**);
`tax_code` FK `"accounting.TaxCode"` SET_NULL null blank same;
`source_submission` FK `"procurement.VendorInvoiceSubmission"` SET_NULL null blank **editable=False** same;
`document` FK `"core.Document"` SET_NULL null blank same;
`duplicate_of` FK `"self"` SET_NULL null blank **editable=False** `related_name="duplicates"`;
`invoice_type` Char(20) INVOICE_TYPE_CHOICES default `"standard"`;
`invoice_number` Char(64) (the SUPPLIER's number — the duplicate key);
`invoice_number_norm` Char(64) **editable=False** `db_index=True`;
`external_ref` Char(64) blank;
`invoice_date` DateField **required**;
`posting_date` DateField null blank;
`due_date` DateField null blank **editable=False**;
`discount_date` DateField null blank **editable=False**;
`discount_expiry_date` DateField null blank **editable=False**;
`discount_base` Char(10) DISCOUNT_BASE_CHOICES default `"net_of_tax"`;
`discount_grace_days` PositiveSmallIntegerField default `0`;
`subtotal` / `tax_total` / `total` / `amount_paid` Decimal(18,2) default `ZERO` **editable=False**;
`fx_rate` Decimal(14,6) null blank `validators=[MinValueValidator(ZERO)]`;
`match_basis` Char(10) MATCH_BASIS_CHOICES default `"none"` (**excluded from the form, written only by `run_match()`**);
`match_status` Char(20) MATCH_STATUS_CHOICES default `"not_run"` **editable=False**;
`match_notes` TextField blank **editable=False**;
`status` Char(20) STATUS_CHOICES default `"draft"`;
`source` Char(20) SOURCE_CHOICES default `"manual"`;
`extraction_confidence` Decimal(5,2) null blank `validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))]`;
`extraction_raw_text` TextField blank;
`notes` TextField blank;
`approved_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**
`related_name="procurement_supplier_invoices_approved"`;
`approved_at` DateTimeField null blank **editable=False**.

`Meta`: `ordering = ["-invoice_date","-id"]`; `unique_together = ("tenant","number")`;
`indexes = [prc_siv_tnt_status_idx (tenant,status), prc_siv_tnt_match_idx (tenant,match_status),
prc_siv_tnt_dup_idx (tenant,vendor,invoice_number_norm), prc_siv_tnt_disc_idx (tenant,discount_date),
prc_siv_tnt_due_idx (tenant,due_date)]`; `verbose_name = "supplier invoice"`.

### Tolerance constants (class attributes)

```python
PRICE_TOL_PCT_UPPER = Decimal("2.00")
PRICE_TOL_PCT_LOWER = None            # no floor — under-billing is not a risk
PRICE_TOL_ABS_UPPER = None            # absolute band ships None (orchestrator decision)
QTY_TOL_PCT_UPPER   = Decimal("0.00") # invoiced vs RECEIVED — never pay for more than arrived
QTY_TOL_ABS_UPPER   = None
QTY_TOL_PCT_UPPER_NO_GRN = Decimal("5.00")
QTY_TOL_PCT_LOWER   = Decimal("5.00")
TOTAL_TOL_PCT       = Decimal("1.00")
TOTAL_TOL_ABS       = None
FX_TOL_PCT          = Decimal("1.00")
TAX_TOL_ABS         = Decimal("1.00") # KEPT — see note below
DUPLICATE_WINDOW_DAYS      = 90
DUPLICATE_AMOUNT_TOL_PCT   = Decimal("1.00")
DISCOUNT_GRACE_DAYS        = 0
DISCOUNT_ANNUALISATION_DAYS = 360
TERMINAL_STATUSES = ("paid", "void", "reversed")
EDITABLE_STATUSES = ("draft", "parked", "captured")
```
**`DATE_TOL_DAYS` is DROPPED** — no `VARIANCE_TYPE_CHOICES` member consumes it. Do not declare it.
**`TAX_TOL_ABS` is the ONE absolute band retained** (flagged to the orchestrator): it has no percentage
counterpart, and shipping it as `None` would make every tax rounding cent a `block`, directly
contradicting research §8.2 ("never block an invoice on tax rounding alone"). Every other absolute
band ships `None`, and the resolver tolerates `None` as "no band".

### Resolver (module-level, "more restrictive wins")

```python
def resolve_tolerance(expected, actual, *, pct_upper=None, pct_lower=None,
                      abs_upper=None, abs_lower=None, cap=None):
    """Return (outcome, variance_abs, variance_pct, tol_pct_applied, tol_abs_applied)."""
```
- `variance_abs = (actual - expected).quantize(Decimal("0.0001"))` (SIGNED: actual − expected)
- `variance_pct = (variance_abs / expected * 100).quantize(Decimal("0.0001"))` when `expected` else `None`
- upper breach ⇔ `(pct_upper is not None and variance_pct is not None and variance_pct > pct_upper)`
  **OR** `(abs_upper is not None and variance_abs > abs_upper)` — **either** firing is a breach
  (more restrictive wins); a `None` band never breaches.
- lower breach ⇔ the mirror with `pct_lower` / `abs_lower` and `< -band`.
- `outcome = "block"` when breached, else `"warn"` when `variance_abs != ZERO`, else `"auto_accept"`.
- `cap="warn"` downgrades a `block` to `"warn"` (used for `tax` and `duplicate` only).
- `tol_pct_applied` / `tol_abs_applied` echo back the bands actually used (`None` when unused).

### Derived / actions (exact names & signatures)

- `@staticmethod normalise_invoice_number(value)` → `"".join(c for c in (value or "").upper() if c.isalnum())[:64]`
- `save(*args, **kwargs)` — sets `invoice_number_norm`; then, when `invoice_date` **and**
  `payment_term_id`: `due_date = invoice_date + timedelta(days=int(pt.days_due or 0))`;
  `discount_date = invoice_date + timedelta(days=int(pt.discount_days))` **only when** `pt.discount_days`,
  and `discount_expiry_date = discount_date + timedelta(days=int(self.discount_grace_days or 0))`;
  clears all three to `None` when either is missing. Then `super().save()`.
- `clean()` — tenant checks on `vendor`, `purchase_order`, `goods_receipt`, `bill`, `journal_entry`,
  `payment_term`, `tax_code`, `document`, `source_submission`, `duplicate_of` (**skip `currency`**);
  **vendor agreement (L40 §3)**: `po.vendor_id != vendor_id` → error on `purchase_order`;
  `grn.purchase_order.vendor_id != vendor_id` → error on `goods_receipt`; `posting_date >= invoice_date`
  when both; `fx_rate` must be finite and `> 0`; `discount_grace_days` 0–365;
  `duplicate_of_id != self.pk`; sign consistency of lines (below); `invoice_number` non-blank.
- `recalc_totals(save=True)` — `subtotal = q2(sum(l.line_total))`;
  `tax_total = q2(sum(q2(l.line_total * (l.tax_rate_pct or ZERO) / 100) for l in lines))`;
  `total = q2(subtotal + tax_total)`; `amount_paid = self.bill.amount_paid() if self.bill_id else ZERO`.
  Uses `update_fields`, so it cannot loop with `SupplierInvoiceLine.save()`.
- `@property is_locked` ⇔ `status in ("paid","void","reversed")`
- `@classmethod cumulative_invoiced_qty(cls, po_line)` —
  `SupplierInvoiceLine.objects.filter(po_line=po_line).exclude(invoice__status__in=TERMINAL_STATUSES)
  .exclude(invoice__invoice_type="credit_memo").aggregate(s=Sum("quantity"))["s"] or ZERO`
- `@classmethod cumulative_received_qty(cls, po_line)` —
  `po_line.receipt_lines.exclude(goods_receipt__status="cancelled").aggregate(s=Sum("quantity_received"))["s"] or ZERO`
- `discount_amount()` — `base = subtotal if discount_base=="net_of_tax" else total`;
  `q2(abs(base) * (pt.discount_pct or ZERO) / Decimal("100"))`
- `annualised_pct()` — `ZERO` unless `payment_term_id`, `pt.discount_pct > 0` and
  `pt.days_due > pt.discount_days`; else
  `q2(pct/(Decimal("100")-pct) * (Decimal(360)/Decimal(days_due-discount_days)) * Decimal("100"))`
  (**2/10 Net 30 ⇒ 36.73**)
- `duplicate_candidates(limit=10)` → `[(invoice, [reason, ...]), ...]`. Reasons drawn from
  `"same vendor"`, `"normalised invoice number matches"`, `"amount within 1%"`,
  `f"invoice date within {DUPLICATE_WINDOW_DAYS} days"`. A candidate is returned only when it scores
  **≥3** reasons (number match is mandatory). **Never auto-rejects** (§8.1).
- `run_match(user=None)` → `(status, {"auto_accept": n, "warn": n, "block": n})`, described below.
- `ALLOWED_TRANSITIONS` (dict, enforced in the VIEW):
  `draft→(parked,captured,void) · parked→(draft,captured,void) · captured→(blocked,pending_approval,void) ·
   blocked→(pending_approval,disputed,void) · disputed→(blocked,pending_approval,void) ·
   pending_approval→(approved,blocked,void) · approved→(scheduled,void,reversed) ·
   scheduled→(paid,approved,void) · paid→(reversed,) · void→() · reversed→()`
- Actions (each **re-checks its own guard internally and returns `bool`**; each
  `save(update_fields=[...])`):
  `park()` draft→parked · `unpark()` parked→draft · `capture()` draft|parked→captured ·
  `block(reason="")` captured|disputed|pending_approval→blocked (writes `match_notes`) ·
  `raise_dispute()` blocked→disputed (requires ≥1 open variance) ·
  `submit_for_approval()` captured|disputed→pending_approval ·
  `approve(user)` pending_approval→approved (**the ONLY ledger-writing transition**) ·
  `send_back(reason="")` pending_approval→blocked · `schedule()` approved→scheduled ·
  `unschedule()` scheduled→approved · `mark_paid()` scheduled→paid ·
  `void(user, reason="")` any non-terminal→void · `reverse(user)` paid|approved→reversed
- `override(user)` — `blocked→pending_approval`; **@tenant_admin_required in the view**; resolves every
  `resolution="open"` variance with `outcome="block"` to `resolution="accepted"`; writes `match_notes`.

### `run_match()` — the ordered check sequence (first breach wins)

Guard: `if self.is_locked: return (self.status, empty_counts)`.
If `invoice_type == "credit_memo"`: delete `self.variances`, set `match_status="not_run"`,
`match_notes="Credit memos are not three-way matched."`, return — **do not touch `status`**.
Otherwise, inside `transaction.atomic()` and under `select_for_update()`:
1. `self.variances.all().delete()`
2. Set `match_basis`: `"none"` when `purchase_order_id is None`; else `"quantity"` when
   `goods_receipt_id` or any line has `receipt_line_id`; else `"amount"`.
3. Vendor agreement (header-level, `basis="header"`, `outcome="block"`):
   PO vendor mismatch → `variance_type="missing_po"`; GRN vendor mismatch → `variance_type="missing_receipt"`.
4. Per line, in this order, `continue` to the next line on the first `block`:
   1. `missing_po` — `match_basis != "none"` and no `po_line` → `block`
   2. `missing_receipt` — `match_basis == "quantity"`, no `receipt_line` → compare `quantity` vs
      `po_line.quantity` with `pct_upper=QTY_TOL_PCT_UPPER_NO_GRN`
   3. `quantity` — compare `quantity` vs `receipt_line.quantity_received`
      (`QTY_TOL_PCT_UPPER`, `abs_upper=QTY_TOL_ABS_UPPER`) **AND** `cumulative_invoiced_qty(po_line)`
      vs `cumulative_received_qty(po_line)` (same bands)
   4. `over_invoice` — `cumulative_invoiced_qty(po_line) > po_line.quantity + allowance` → `block`
      (allowance = `po_line.quantity * QTY_TOL_PCT_UPPER/100`)
   5. `price` — `unit_price` vs `po_line.unit_price` (`pct_upper=PRICE_TOL_PCT_UPPER`,
      `pct_lower=PRICE_TOL_PCT_LOWER`, `abs_upper=PRICE_TOL_ABS_UPPER`)
   `match_basis == "amount"` **skips steps 2–4**. `match_basis == "none"` skips 1–5 but emits a
   `block` variance of `variance_type="missing_po"`, `message="Non-PO line requires a GL account."`
   for every line with no `gl_account`.
5. Header level: `total_amount` (Σ expected line value vs `total`, `TOTAL_TOL_PCT`/`TOTAL_TOL_ABS`);
   `fx_rate` (only when `currency_id != purchase_order.currency_id`, `FX_TOL_PCT`);
   `tax` (`TAX_TOL_ABS`, **`cap="warn"`** — tax rounding never blocks);
   `duplicate` (from `duplicate_candidates()`, **`cap="warn"`**).
6. Outcome → status: any `block` → `status="blocked"`; elif a duplicate variance exists →
   `status="blocked"`, `match_status="duplicate_suspect"`; else `status="pending_approval"`.
7. `match_status` from the FIRST `block` variance's type (first breach wins), else
   `"within_tolerance"` when any `warn` else `"matched"`. Map:
   `price→price_variance` · `quantity|quantity_no_receipt→quantity_variance` ·
   `over_invoice→over_invoiced` · `total_amount→total_variance` · `fx_rate→fx_variance` ·
   `missing_receipt→no_receipt` · `missing_po→not_run` · `duplicate→duplicate_suspect` · `tax→within_tolerance`.
8. Set `matched_qty` on each line (accepted quantity = min(invoiced, received-or-ordered)).

### The approve/post path (§8.10)

`approve(user)` runs inside `transaction.atomic()` on a `select_for_update()` row and begins with
`if self.journal_entry_id: return False` (double-click / back-button guard).
It then: (a) stamps `approved_by`, `approved_at`, `posting_date = posting_date or timezone.localdate()`;
(b) creates **one** `accounting.Bill` (`party=self.vendor`, `payment_terms=self.payment_term`,
`bill_date=self.invoice_date`, `due_date=self.due_date`, `currency=self.currency`, `status="approved"`,
`document=self.document`) and one `BillLine` per invoice line; calls `bill.recalc_totals()`;
(c) creates **one** `accounting.JournalEntry` (`entry_type="invoice"`, `status="posted"`,
`entry_date=self.posting_date`, `reference=self.invoice_number`, `description=f"Supplier invoice {self.number}"`,
`created_by=user`) with **balanced** `JournalLine` rows: Debit the expense/GRN-clearing account for
`subtotal`, Debit/Credit tax as applicable, Credit the AP control liability for `total`, and — when a
discount is taken — Debit AP and Credit a purchase-discounts-received account so the entry balances
either way. **GL resolution:** `JournalLine.gl_account` is `PROTECT` and non-nullable, and `GLAccount`
carries no AP/cash subtype, so resolve with
`_gl_account(tenant, codes, account_type)` = `GLAccount.objects.filter(tenant=tenant, is_active=True, code__in=codes).first()`
falling back to `filter(tenant=tenant, is_active=True, account_type=account_type).order_by("code").first()`.
If any required account resolves to `None`, raise `ValidationError("No <expense|AP control|tax> GL account
is configured for this workspace — the invoice was not posted.")` — the transaction rolls back, so **no
partial entry and no Bill**. **Never** write `scm.GoodsReceiptNote.bill` (6.12 owns that field, §8.11).
`reverse(user)` mirrors this with `entry_type="reversal"`, `reversal_of=self.journal_entry`, and swapped
debits/credits; it never edits the original entry.

## FORM (lane A)

`SupplierInvoiceForm(TenantUniqueMixin, TenantModelForm)` — `Meta.model = SupplierInvoice`;
`Meta.fields = ["vendor","purchase_order","goods_receipt","payment_term","currency","tax_code",
"invoice_type","invoice_number","external_ref","invoice_date","posting_date","discount_base",
"discount_grace_days","fx_rate","notes"]`.
**EXCLUDED (system-set):** tenant, number, bill, journal_entry, source_submission, duplicate_of,
invoice_number_norm, due_date, discount_date, discount_expiry_date, subtotal, tax_total, total,
amount_paid, match_basis, match_status, match_notes, status, source, extraction_confidence,
extraction_raw_text, approved_by, approved_at.
`__init__(self, *args, tenant=None, **kwargs)`: narrow `purchase_order`, `goods_receipt`, `payment_term`,
`tax_code`, `document`, `source_submission`, `vendor` to the tenant (auto-done except `vendor`, which
`TenantModelForm` handles); leave `currency` alone. On EDIT (`self.instance.pk`) **pop**
`purchase_order` and `goods_receipt` when `instance.status not in EDITABLE_STATUSES`.
Override `add_error()` with the 6.12 remap (`forms/GoodsReceiptInspection/ReceiptDiscrepancies.py:153`)
so an error keyed on a popped field becomes a non-field error instead of `ValueError`.
`clean()`: `_reject_foreign(self, cleaned, ["vendor","purchase_order","goods_receipt","payment_term",
"tax_code"])`; the vendor-agreement check; then Decimal safety on `fx_rate`.

`SupplierInvoiceLineFormSet = inlineformset_factory(SupplierInvoice, SupplierInvoiceLine,
form=SupplierInvoiceLineForm, fields=[...], extra=1, can_delete=True)` — **prefix `"lines"`**
(the inline default, since the child FK declares `related_name="lines"`).

`CaptureUploadForm(forms.Form)` — `document_file = forms.FileField()`; validate the extension against
`apps.core.forms.ALLOWED_DOC_EXTENSIONS` and the size against `MAX_UPLOAD_BYTES` (import these two
names **locally** inside `clean_document_file`, exactly as 6.12 does — they are not package re-exports).

**Decimal safety (L35) — mandatory on every hand-parsed money field:**
```python
from decimal import Decimal, InvalidOperation
_MONEY_CEILING = Decimal(10) ** 16          # Decimal(18,2)
def _safe_decimal(raw, ceiling, label):
    """Return (value, error_or_None). L35: is_finite(), magnitude cap, explicit rejection branch."""
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, ArithmeticError, TypeError):
        return None, f"Enter a valid number for {label}."
    if not value.is_finite():
        return None, f"Enter a finite number for {label}."
    if abs(value) >= ceiling:
        return None, f"{label} is too large."
    return value, None
```
Every money field is also declared as `forms.DecimalField(max_digits=…, decimal_places=…,
min_value=…)`.

## VIEWS (lane A) — names and context keys pinned

All `@login_required`; privileged ones add `@tenant_admin_required` **and** `@require_POST`
(order: `@login_required` / `@tenant_admin_required` / `@require_POST`). Every queryset is
`filter(tenant=request.tenant)` — never `.all()`.

- **`supplierinvoice_list`** — `crud_list` over
  `SupplierInvoice.objects.filter(tenant=request.tenant).select_related("vendor","purchase_order","currency","payment_term")`.
  `search_fields=["number","invoice_number","invoice_number_norm","external_ref","vendor__name"]`.
  `filters=[("status","status",False),("match_status","match_status",False),("vendor","vendor_id",True),
  ("source","source",False),("invoice_type","invoice_type",False)]`.
  `extra_context` keys: `status_choices`, `match_status_choices`, `source_choices`,
  `invoice_type_choices`, `vendors` (=`Party.objects.filter(tenant=request.tenant).order_by("name")`),
  `stats` (ONE `.aggregate()`; keys **`total`, `blocked`, `disputed`, `pending_approval`, `overdue`**).
  → plus crud_list's `object_list`, `page_obj`, `q`.
- **`supplierinvoice_detail`** — hand-rolled `render` (NOT `crud_detail`). Context keys:
  `obj` (the invoice), `lines`, `variances`, `disputes`, `bill`, `journal_entry`,
  `duplicate_candidates`, `discount` (dict keys **`base_amount`, `amount`, `payable_if_discounted`,
  `days_to_discount`, `annualised_pct`, `capturable`**), `allowed_transitions` (list of status strings),
  `is_locked`, `tolerances` (dict keys **`price_pct_upper`, `price_pct_lower`, `price_abs_upper`,
  `qty_pct_upper`, `qty_abs_upper`, `qty_pct_upper_no_grn`, `qty_pct_lower`, `total_pct`, `total_abs`,
  `fx_pct`, `tax_abs`, `duplicate_window_days`, `duplicate_amount_tol_pct`,
  `discount_annualisation_days`**), `can_edit`, `can_match`, `can_override`, `can_approve`,
  `can_void`, `can_reverse`, `is_admin`.
- **`supplierinvoice_create` / `supplierinvoice_edit`** — hand-rolled `_invoice_form(request, instance=None)`.
  Context: `form`, `line_formset`, `obj`, `is_edit`, `title`, `submit_label`, `cancel_url`.
  Stamps nothing user-choosable; refuses edit when `not instance.status in EDITABLE_STATUSES`
  (`messages.error` + redirect to detail).
- **`supplierinvoice_delete`** — `@login_required @tenant_admin_required @require_POST`, `crud_delete`
  → `success_url="procurement:supplierinvoice_list"`. **No confirm template**; the list row's
  `onsubmit="return confirm('Delete {{ obj.number }}? …')"` uses the system `SIV-` number (L42).
- **`supplierinvoice_capture`** (GET + POST, page titled **"Capture Invoice"** — the UI must never say
  "OCR"). Two-stage POST via a hidden `stage` field (`"upload"` / `"confirm"`).
  Context keys: `stage`, `upload_form`, `form`, `document`, `extraction`, `confidence`, `source`,
  `has_text_layer`, `warnings`, `raw_text`, `title`, `cancel_url`.
  `extraction` is a dict whose keys are EXACTLY: `invoice_number`, `invoice_date`, `due_date`,
  `po_number`, `subtotal`, `tax_total`, `total`, `currency_code`, `vendor_name`; each value is
  `{"value": <str>, "confidence": <"high"|"medium"|"low"|"none">}`.
  `warnings` is `list[str]`. `confidence` is a `Decimal` 0–100 or `None`.
  **PDF extraction:** `try: import pdfplumber except ImportError: pdfplumber = None`.
  **`pdfplumber` is NOT in `requirements.txt`** — it will be `None` in every current deployment, so the
  designed path is `has_text_layer=False`, `source="manual"`, `extraction_confidence=0`, `warnings`
  carrying one honest line, and the page renders the normal create form pre-filled with nothing.
  When it IS present: `pdfplumber.open(path)` → `"\n".join(p.extract_text() or "" for p in pages)`;
  `""`/`None` ⇒ no text layer ⇒ same manual path. Run anchor+regex heuristics for header fields and
  `extract_tables()` for line items; every extracted value stays editable.
- **`supplierinvoice_duplicates`** — context `groups` (list of dicts with keys **`invoice`,
  `candidates`, `count`**; each candidate is `{"invoice":…, "reasons":[str]}`), `page_obj`,
  `window_days` (=`SupplierInvoice.DUPLICATE_WINDOW_DAYS`), `stats` (dict keys **`scanned`, `suspect`,
  `linked`**).
- **`supplierinvoice_match`** — `@require_POST`; runs `obj.run_match(request.user)` under
  `select_for_update()`, `messages` with the counts, `write_audit_log(..., "update", {"action":"match"})`,
  redirect to detail.
- **`supplierinvoice_revalidate`** — `@tenant_admin_required @require_POST`; re-runs `run_match()` for
  every tenant invoice with `status__in=("blocked","captured")`; `messages` with the counts; redirect
  to `procurement:matchvariance_list`.
- **`supplierinvoice_approve`** / **`_override`** / **`_void`** / **`_reverse`** — `@tenant_admin_required
  @require_POST`; fetch under `select_for_update()`, call the action, on `False` `messages.error` else
  `messages.success` + `write_audit_log(request.user, obj, "update", {"action": "<verb>"})`; redirect to
  detail. `void` reads `request.POST.get("reason","")`.
- **`supplierinvoice_schedule`** / **`supplierinvoice_mark_paid`** — `@require_POST`
  (`mark_paid` also `@tenant_admin_required`).
- **`invoicevoucher_dashboard`** — context `tiles` (list of dicts keys **`label`, `url`, `icon`,
  `count`**), `stats` (keys **`invoices`, `blocked`, `disputed`, `capturable_discount`,
  `open_disputes`**), `recent` (last 8 invoices), `blocked` (invoices with `status="blocked"`),
  `expiring` (capturable discounts due in ≤7 days), `open_disputes`, `aging` (dict of bucket key→count).

## URLS (lane A) — literal routes BEFORE `<int:pk>`

```
supplier-invoices/                       supplierinvoice_list
supplier-invoices/add/                   supplierinvoice_create
supplier-invoices/duplicates/            supplierinvoice_duplicates
supplier-invoices/revalidate/            supplierinvoice_revalidate
supplier-invoices/<int:pk>/              supplierinvoice_detail
supplier-invoices/<int:pk>/edit/         supplierinvoice_edit
supplier-invoices/<int:pk>/delete/       supplierinvoice_delete
supplier-invoices/<int:pk>/match/        supplierinvoice_match
supplier-invoices/<int:pk>/approve/      supplierinvoice_approve
supplier-invoices/<int:pk>/override/     supplierinvoice_override
supplier-invoices/<int:pk>/void/         supplierinvoice_void
supplier-invoices/<int:pk>/reverse/      supplierinvoice_reverse
supplier-invoices/<int:pk>/schedule/     supplierinvoice_schedule
supplier-invoices/<int:pk>/mark-paid/    supplierinvoice_mark_paid
capture/                                 supplierinvoice_capture
invoice-vouchers/                        invoicevoucher_dashboard
```

## TEMPLATES (lane A)

`supplierinvoice/list.html` — 5 stat cards (blue `file-text` total · red `ban` blocked · amber
`message-square-warning` disputed · orange `clock` pending approval · slate `alert-triangle` overdue);
filter bar (q, status, match_status, vendor pk-select with `|stringformat:"d"`, source, invoice_type);
columns Number+date · Vendor · PO/GRN · Invoice no. · Total (currency code + `total`) · Discount date ·
Match status badge · Status badge · Actions (eye/pencil/trash-2). `{% include "partials/pagination.html" %}`.
`supplierinvoice/detail.html` — `<dl class="detail-grid">` header block; lines table (description, PO
line, receipt line, qty, unit price, line_total, GL/tax, cumulative invoiced vs received); variances
table; disputes table; attachment link (`{% if obj.document %}`); `discount` panel; `tolerances` panel;
`duplicate_candidates` panel; side Actions with POST forms gated on `can_*`.
`supplierinvoice/form.html` — two-column form-groups + the `lines` formset table.
`capture.html` — upload card (stage=upload), then the review card: side-by-side extracted value +
confidence badge per field, every field editable, `warnings` list, collapsible `raw_text` `<pre>`.
`duplicates.html` — grouped `groups` cards with per-candidate reason chips.
`dashboard.html` — tile grid from `tiles`, four stat cards, recent/blocked/expiring/disputes panels.

Badge maps (model class attributes, use `obj.status_css` etc.):
`STATUS_CSS` draft→badge-muted · parked→badge-slate · captured→badge-info · blocked→badge-red ·
disputed→badge-amber · pending_approval→badge-amber · approved→badge-green · scheduled→badge-info ·
paid→badge-green · void→badge-slate · reversed→badge-slate.
`MATCH_STATUS_CSS` not_run→badge-muted · matched→badge-green · within_tolerance→badge-info ·
price_variance/quantity_variance/total_variance/fx_variance/no_receipt→badge-amber ·
over_invoiced/duplicate_suspect→badge-red.
`SOURCE_CSS` manual→badge-muted · pdf_text_layer→badge-info · e_invoice_xml→badge-info ·
vis→badge-slate · ocr→badge-slate.

---

# LANE B — SupplierInvoiceLine (plain child, no number, no tenant column)

Files: `apps/procurement/{models,forms,views,urls}/InvoiceVoucherManagement/SupplierInvoiceLines.py`
+ `templates/procurement/invoicevouchermanagement/supplierinvoiceline/{list,detail,form}.html`
+ `templates/procurement/invoicevouchermanagement/payment_schedule.html`

## MODEL `SupplierInvoiceLine(models.Model)` — mirrors `scm.GoodsReceiptLine` (NO tenant, NO number)

`invoice` FK `SupplierInvoice` CASCADE `related_name="lines"`;
`po_line` FK `"scm.PurchaseOrderLine"` PROTECT null blank `related_name="procurement_invoice_lines"`;
`receipt_line` FK `"scm.GoodsReceiptLine"` PROTECT null blank `related_name="procurement_invoice_lines"`;
`item` FK `"scm.Item"` SET_NULL null blank `related_name="procurement_invoice_lines"` (**optional** —
the free-text fallback stays);
`gl_account` FK `"accounting.GLAccount"` SET_NULL null blank `related_name="procurement_invoice_lines"`;
`tax_code` FK `"accounting.TaxCode"` SET_NULL null blank `related_name="procurement_invoice_lines"`;
`description` Char(255) blank; `sku_hint` Char(64) blank; `uom_hint` Char(32) blank;
`quantity` Decimal(14,4) default `Decimal("1")`;
`unit_price` Decimal(14,2) default `ZERO` (**NO `MinValueValidator`** — credit memos are negative);
`tax_rate_pct` Decimal(5,2) default `ZERO` `validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("100"))]`;
`line_total` Decimal(18,2) default `ZERO` **editable=False**;
`matched_qty` Decimal(14,4) default `ZERO` **editable=False**.

**`cumulative_invoiced_qty` is a DERIVED `@property`, NOT a column** (orchestrator decision — a stored
counter drifts the first time a GRN is cancelled or an invoice is reversed). Same for
`cumulative_received_qty`; both delegate to `SupplierInvoice.cumulative_*_qty(self.po_line)` and return
`ZERO` when `po_line_id` is `None`.

`Meta`: `ordering = ["id"]`; `indexes = [prc_sivl_invoice_idx (invoice), prc_sivl_poline_idx (po_line)]`
(the second backs the over-invoicing scan, §8.5); `verbose_name = "supplier invoice line"`.

`save()`: `line_total = q2((self.quantity or ZERO) * (self.unit_price or ZERO))` (**signed, no `abs()`**);
mirror `description`/`sku_hint`/`uom_hint` from `po_line` when blank (the `AsnLine.save()` shape),
skipped when `update_fields` is passed; `super().save()`; then, **only when `update_fields is None`**,
`self.invoice.recalc_totals()`.

`clean()`: `po_line.purchase_order_id == self.invoice.purchase_order_id` when both set;
`receipt_line.po_line_id == self.po_line_id` when both set;
`receipt_line.goods_receipt.tenant_id == self.invoice.tenant_id` (the line has no tenant of its own);
`item.tenant_id == invoice.tenant_id`; `gl_account` / `tax_code` tenant checks;
`quantity` and `unit_price` finite and within `10**10` / `10**12`;
sign consistency with the header's `invoice_type` (credit memo ⇒ `quantity*unit_price <= 0`,
otherwise `>= 0`); `match_basis == "none"` ⇒ `gl_account` required.

Properties: `cumulative_invoiced_qty`, `cumulative_received_qty`, `tax_amount`
(=`q2(line_total*(tax_rate_pct or ZERO)/100)`), `gross_total` (=`q2(line_total + tax_amount)`),
`is_matched` (=`matched_qty == quantity`).

## FORM / VIEWS / URLS (lane B)

`SupplierInvoiceLineForm(TenantModelForm)` (NO `TenantUniqueMixin` — the child has no tenant):
`Meta.fields = ["po_line","receipt_line","item","description","sku_hint","uom_hint","quantity",
"unit_price","tax_rate_pct","gl_account","tax_code"]`. `__init__` narrows
`po_line` to `PurchaseOrderLine.objects.filter(purchase_order__tenant=tenant)` (and to the invoice's PO
once set), `receipt_line` to `GoodsReceiptLine.objects.filter(goods_receipt__tenant=tenant)`
(and to `po_line`'s receipts once set), `item`/`gl_account`/`tax_code` to the tenant.
`clean()` re-checks all three header-scoped FKs explicitly.

- **`supplierinvoiceline_list`** — `crud_list` over
  `SupplierInvoiceLine.objects.filter(invoice__tenant=request.tenant).select_related("invoice","po_line","receipt_line","item","gl_account")`;
  `search_fields=["description","sku_hint","invoice__number","invoice__invoice_number"]`;
  `filters=[("invoice","invoice_id",True),("po_line","po_line_id",True),("item","item_id",True),
  ("has_gl","gl_account__isnull",False)]`;
  extra: `invoices` (tenant's invoices, `[:200]`), `items`, `stats` (keys **`lines`, `matched`,
  `unmatched`, `non_po`**).
- **`supplierinvoiceline_detail`** — context `obj`, `invoice`, `variances`, `cumulative` (dict keys
  **`invoiced`, `received`, `ordered`, `remaining`**), `can_edit`.
- **`supplierinvoiceline_create` / `_edit`** — hand-rolled `_line_form(request, invoice_pk=None,
  instance=None)`; create requires `?invoice=<pk>` validated with `as_db_int` + a tenant existence
  check; context `form`, `obj`, `invoice`, `is_edit`, `title`, `submit_label`, `cancel_url`.
- **`supplierinvoiceline_delete`** — `@login_required @require_POST`, `crud_delete` → redirect to
  `procurement:supplierinvoice_detail` with the invoice pk.
- **`paymentschedule_list`** — **hand-rolled** (a bucketed projection, not a register). URL
  `payment-schedule/`, name `paymentschedule_list`, template `payment_schedule.html`.
  GET params: `q`, `vendor` (int), `terms` (int), `weeks` (int, default 8, clamped 1–26).
  Queryset: `SupplierInvoice.objects.filter(tenant=request.tenant,
  status__in=("approved","scheduled")).exclude(due_date=None).select_related("vendor","currency","payment_term").order_by("due_date","id")`
  (filtered by `vendor_id` / `payment_term_id` / search before bucketing).
  Buckets: one "Overdue" bucket (`due_date < today`) plus `horizon_weeks` weekly buckets.
  Context keys: `buckets` (list of dicts with keys **`key`, `label`, `start`, `end`, `rows`, `count`,
  `total`**), `page_obj` (from `paginate(request, flat_rows)`), `total_payable`,
  `terms` (=`PaymentTerm.objects.filter(tenant=request.tenant, is_active=True).order_by("name")`),
  `currency` (=`Currency.objects.filter(pk__in=qs.values("currency_id")).first() or Currency.objects.first()`),
  `vendors`, `stats` (keys **`invoices`, `total_payable`, `overdue_total`, `discounted_total`**),
  `horizon_weeks`, `today`, `q`.

URLs: `supplier-invoice-lines/` (list) · `add/` · `<int:pk>/` · `<int:pk>/edit/` ·
`<int:pk>/delete/`, names `supplierinvoiceline_*`. Plus `payment-schedule/` → `paymentschedule_list`.

## TEMPLATES (lane B)

`supplierinvoiceline/list.html` — stat cards (blue `layers` lines · green `check-circle` matched ·
amber `alert-triangle` unmatched · slate `file-text` non-PO); filters (q, invoice, item, has_gl);
columns Line (description + invoice link) · PO line · Receipt line · Qty · Unit price · Line total ·
Cumulative invoiced/received · GL account · Actions.
`detail.html` — `<dl class="detail-grid">` of every field + the `cumulative` comparison panel +
its variances.
`form.html` — single form, prefix `lines` when embedded.
`payment_schedule.html` — one card per bucket with `count` + `total` in the header, a `<table>` of
`rows` (invoice number, vendor, due date, terms, total, discount capturable), the `total_payable`
summary row, and the vendor/terms/weeks filter bar.

---

# LANE C — InvoiceMatchVariance (TenantOwned, no number)

Files: `apps/procurement/{models,forms,views,urls}/InvoiceVoucherManagement/MatchVariances.py`
+ `templates/procurement/invoicevouchermanagement/matchvariance/{list,detail}.html`
+ `templates/procurement/invoicevouchermanagement/match_board.html`
**This lane ships TWO entity templates, NOT THREE — there is no create/edit/delete route or `form.html`.**

## MODEL `InvoiceMatchVariance(TenantOwned)`

CHOICES verbatim:
```python
VARIANCE_TYPE_CHOICES = [("price","Unit Price"),("quantity","Quantity vs Receipt"),
    ("quantity_no_receipt","Quantity vs Order (No Receipt)"),("over_invoice","Cumulative Over-Invoicing"),
    ("total_amount","Header Total"),("fx_rate","FX / Conversion Rate"),("tax","Tax Amount"),
    ("duplicate","Duplicate Invoice"),("missing_po","No PO Reference"),("missing_receipt","No Goods Receipt")]
OUTCOME_CHOICES = [("auto_accept","Auto-Accepted (Within Tolerance)"),("warn","Accepted With Warning"),
    ("block","Blocked — Outside Tolerance")]
RESOLUTION_CHOICES = [("open","Open"),("accepted","Accepted by AP"),("disputed","Disputed With Supplier"),
    ("credit_memo","Resolved by Credit Memo"),("debit_memo","Resolved by Debit Memo"),
    ("short_paid","Resolved by Short Payment"),("cancelled","Cancelled")]
BASIS_CHOICES = [("po","Purchase Order"),("receipt","Goods Receipt"),("header","Invoice Header")]
```

`invoice` FK `SupplierInvoice` CASCADE `related_name="variances"`;
`invoice_line` FK `SupplierInvoiceLine` CASCADE null blank `related_name="variances"`
(null ⇒ header-level check);
`dispute` FK `InvoiceDispute` SET_NULL null blank `related_name="variances"`;
`variance_type` Char(20) VARIANCE_TYPE_CHOICES;
`basis` Char(20) BASIS_CHOICES default `"po"`;
`expected_value` Decimal(18,4) default `ZERO`; `actual_value` Decimal(18,4) default `ZERO`;
`variance_abs` Decimal(18,4) default `ZERO` **editable=False** (SIGNED: actual − expected);
`variance_pct` Decimal(9,4) null blank **editable=False** (SIGNED %);
`tolerance_abs_applied` Decimal(18,4) null blank;
`tolerance_pct_applied` Decimal(9,4) null blank;
`outcome` Char(12) OUTCOME_CHOICES default `"auto_accept"`;
`resolution` Char(12) RESOLUTION_CHOICES default `"open"`;
`message` Char(255) blank;
`detected_at` DateTimeField `auto_now_add=True`.

`Meta`: `ordering = ["-detected_at","-id"]`; `indexes = [prc_imv_tnt_outcome_idx (tenant,outcome,resolution),
prc_imv_tnt_type_idx (tenant,variance_type), prc_imv_invoice_idx (invoice)]`;
`verbose_name = "invoice match variance"`.

- `save()` derives `variance_abs` / `variance_pct` (see `resolve_tolerance`).
- `clean()`: `invoice.tenant_id == self.tenant_id`; `invoice_line.invoice_id == self.invoice_id`;
  `dispute.tenant_id == self.tenant_id`; tolerance values finite.
- `@classmethod record(cls, *, invoice, invoice_line=None, variance_type, basis, expected, actual,
  pct_upper=None, pct_lower=None, abs_upper=None, abs_lower=None, message="", outcome_override=None,
  cap=None)` → creates and returns the row (the single writer `run_match()` uses).
- `accept(user)` — `resolution` `open|disputed → accepted`; returns `bool`.
- properties `is_blocking` (`outcome=="block"`), `is_open` (`resolution=="open"`), `explain()`
  (human string `"expected X → actual Y (Z%) against band …"`).
- `OUTCOME_CSS` auto_accept→badge-green · warn→badge-amber · block→badge-red.
  `RESOLUTION_CSS` open→badge-amber · accepted→badge-green · disputed→badge-red ·
  credit_memo/debit_memo→badge-info · short_paid→badge-slate · cancelled→badge-muted.

## FORM / VIEWS / URLS (lane C)

`forms/…/MatchVariances.py` exports **one** form: `InvoiceVarianceAcceptForm(forms.Form)` with
`note = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={"class":"form-textarea","rows":2}))`.
No ModelForm — variances are system-generated.

- **`matchvariance_list`** (the exceptions board) — `crud_list` over
  `InvoiceMatchVariance.objects.filter(tenant=request.tenant).select_related("invoice","invoice_line","dispute")`;
  `search_fields=["message","invoice__number","invoice__invoice_number"]`;
  `filters=[("variance_type","variance_type",False),("outcome","outcome",False),
  ("resolution","resolution",False),("basis","basis",False),("invoice","invoice_id",True)]`;
  extra: `variance_type_choices`, `outcome_choices`, `resolution_choices`, `basis_choices`,
  `invoices`, `stats` (keys **`open`, `blocking`, `warn`, `auto_accept`**).
- **`matchvariance_detail`** — context `obj`, `invoice`, `invoice_line`, `dispute`,
  `explanation` (=`obj.explain()`), `tolerance` (dict keys **`abs`, `pct`**), `actions` (list of dicts
  with keys **`url`, `label`, `verb`, `css`**), `can_accept`, `is_admin`.
- **`matchvariance_accept`** — `@login_required @require_POST`; `select_for_update()`, bind
  `InvoiceVarianceAcceptForm`, call `obj.accept(request.user)`, `write_audit_log(... "update",
  {"action":"accept"})`, redirect to detail.
- **`invoice_match_board`** — standalone, URL `match-board/`, name `invoice_match_board`, template
  `match_board.html`. Context: `groups` (list of dicts with keys **`invoice`, `variances`,
  `blocking_count`, `warn_count`, `oldest_at`**), `page_obj`, `stats` (keys **`invoices`, `blocking`,
  `warn`, `overdue`**), `outcome_choices`, `variance_type_choices`, `today`, `q`.

URLs: `match-variances/` · `match-variances/<int:pk>/` · `match-variances/<int:pk>/accept/`,
names `matchvariance_list` / `matchvariance_detail` / `matchvariance_accept`; plus
`match-board/` → `invoice_match_board`.

## TEMPLATES (lane C)

`matchvariance/list.html` — stat cards (blue `scale` open · red `ban` blocking · amber
`alert-triangle` warn · green `check-circle` auto-accepted); filters (q, variance_type, outcome,
resolution, basis, invoice); columns Detected · Invoice · Line · Type badge · Basis ·
Expected → Actual · Variance (abs + pct) · Band applied · Outcome badge · Resolution badge ·
Message · Actions.
`match_board.html` — one card per invoice in `groups`, grouped counts, expandable variance rows.

---

# LANE D — InvoiceDispute [`DSP-`]

Files: `apps/procurement/{models,forms,views,urls}/InvoiceVoucherManagement/InvoiceDisputes.py`
+ `templates/procurement/invoicevouchermanagement/invoicedispute/{list,detail,form}.html`
+ `templates/procurement/invoicevouchermanagement/dispute_aging.html`

## MODEL `InvoiceDispute(TenantNumbered)`, `NUMBER_PREFIX = "DSP"`

```python
REASON_CODE_CHOICES = [("price","Price Dispute"),("quantity","Quantity Dispute"),
    ("goods_not_received","Missing Goods"),("damaged","Damaged / Quality"),("duplicate","Duplicate Invoice"),
    ("credit_not_processed","Credit Not Processed"),("tax","Tax / VAT Error"),
    ("freight","Unapproved Freight or Charges"),("admin","Administrative Error"),("other","Other")]
RESOLUTION_CHOICES = [("credit_memo","Supplier Credit Memo"),("debit_memo","Debit Memo Raised"),
    ("reinvoice","Supplier Re-Invoice"),("short_pay","Short Payment Accepted"),("withdrawn","Dispute Withdrawn")]
STATUS_CHOICES = [("open","Open"),("awaiting_supplier","Awaiting Supplier"),
    ("awaiting_internal","Awaiting Internal Review"),("resolved","Resolved"),("escalated","Escalated"),
    ("closed","Closed")]
```

`invoice` FK `SupplierInvoice` CASCADE `related_name="disputes"`;
`invoice_line` FK `SupplierInvoiceLine` SET_NULL null blank `related_name="disputes"`;
`supplier` FK `"core.Party"` PROTECT `related_name="procurement_invoice_disputes"`;
`reason_code` Char(24) REASON_CODE_CHOICES;
`status` Char(20) STATUS_CHOICES default `"open"` **editable=False**;
`disputed_amount` Decimal(14,2) default `ZERO` `validators=[MinValueValidator(ZERO)]`;
`description` TextField; `supplier_contact` Char(120) blank;
`assigned_to` FK `settings.AUTH_USER_MODEL` SET_NULL null blank
`related_name="procurement_invoice_disputes_assigned"`;
`due_date` DateField null blank;
`raised_by` FK `settings.AUTH_USER_MODEL` SET_NULL null blank **editable=False**
`related_name="procurement_invoice_disputes_raised"`;
`raised_at` DateTimeField `auto_now_add=True`;
`resolved_at` DateTimeField null blank **editable=False**;
`resolution` Char(16) blank RESOLUTION_CHOICES;
`resolution_note` TextField blank;
`credit_memo_invoice` FK `SupplierInvoice` SET_NULL null blank `related_name="resolved_disputes"`.

`SLA_DAYS = 10`. `OPEN_STATUSES = ("open","awaiting_supplier","awaiting_internal","escalated")`.
`Meta`: `ordering = ["-raised_at","-id"]`; `unique_together = ("tenant","number")`;
`indexes = [prc_dsp_tnt_status_idx (tenant,status,due_date), prc_dsp_tnt_supplier_idx (tenant,supplier)]`;
`verbose_name = "invoice dispute"`.

`save()`: denormalise `supplier` from `invoice.vendor` when blank; default
`due_date = timezone.localdate() + timedelta(days=SLA_DAYS)` when `None` and `not self.pk`.
`clean()`: `invoice.tenant_id == self.tenant_id`; `supplier.tenant_id == self.tenant_id`;
`invoice_line.invoice_id == self.invoice_id`; `disputed_amount <= abs(invoice.total)`;
`due_date` finite/valid; `credit_memo_invoice.invoice_type == "credit_memo"`.

Actions (return `bool`, `save(update_fields=[...])`, each re-checks its own guard):
`await_supplier(user)` open|awaiting_internal|escalated→awaiting_supplier ·
`await_internal(user)` open|awaiting_supplier|escalated→awaiting_internal ·
`escalate(user)` open|awaiting_supplier|awaiting_internal→escalated ·
`resolve(user, resolution, note="")` any OPEN→resolved (stamps `resolved_at`, `resolution`,
`resolution_note`; `resolution` must be in `RESOLUTION_CHOICES`) ·
`close(user)` resolved→closed · `withdraw(user, note="")` any OPEN→closed with `resolution="withdrawn"` ·
`link_credit_memo(invoice)` sets `credit_memo_invoice`.

Properties: `is_open`, `days_open` (int, from `raised_at`), `is_overdue`
(`due_date and due_date < timezone.localdate() and is_open`), `age_bucket` (one of
`"overdue"`,`"0-7"`,`"8-14"`,`"15-30"`,`"31-60"`,`"60+"`,`"none"`),
`undisputed_balance` (=`invoice.total - disputed_amount`).
`STATUS_CSS` open→badge-amber · awaiting_supplier→badge-info · awaiting_internal→badge-slate ·
escalated→badge-red · resolved→badge-green · closed→badge-muted.
`REASON_CSS` price/quantity→badge-amber · goods_not_received/damaged/duplicate→badge-red ·
credit_not_processed→badge-info · tax/freight→badge-slate · admin/other→badge-muted.

## FORM / VIEWS / URLS (lane D)

`InvoiceDisputeForm(TenantUniqueMixin, TenantModelForm)`: `Meta.fields = ["invoice","invoice_line",
"reason_code","supplier_contact","disputed_amount","description","assigned_to","due_date"]`.
**EXCLUDED (system-set):** tenant, number, supplier (denormalised in `save()`), status, resolution,
resolution_note, resolved_at, raised_by, raised_at, credit_memo_invoice.
`__init__` narrows `invoice`/`invoice_line`/`assigned_to` to the tenant and `invoice_line` to the
instance's invoice on edit; pops `invoice` and `invoice_line` when `self.instance.pk` (a saved dispute
must not be re-pointed). `clean()`: `_reject_foreign(self, cleaned, ["invoice","invoice_line"])`,
then the `disputed_amount <= abs(invoice.total)` and Decimal-safety checks. Add the 6.12 `add_error()`
remap for popped fields.

- **`invoicedispute_list`** — `crud_list` over
  `InvoiceDispute.objects.filter(tenant=request.tenant).select_related("invoice","invoice_line","supplier","assigned_to")`;
  `search_fields=["number","description","invoice__number","invoice__invoice_number","supplier__name"]`;
  `filters=[("status","status",False),("reason_code","reason_code",False),("supplier","supplier_id",True),
  ("assigned_to","assigned_to_id",True)]`; `?overdue=1` is applied to the queryset **before**
  `crud_list` (`due_date__lt=timezone.localdate()`, `status__in=OPEN_STATUSES`).
  extra: `status_choices`, `reason_choices`, `suppliers`, `assignees`, `stats` (keys **`open`,
  `overdue`, `escalated`, `resolved`**).
- **`invoicedispute_detail`** — context `obj`, `invoice`, `invoice_line`, `variances`,
  `resolution_choices`, `days_open`, `is_overdue`, `actions` (list of dicts keys **`url`, `label`,
  `verb`, `css`**), `can_edit`, `can_resolve`, `is_admin`.
- **`invoicedispute_create` / `_edit`** — hand-rolled `_dispute_form(request, invoice_pk=None,
  instance=None)`; create accepts `?invoice=<pk>` (validated with `as_db_int` + tenant check) and
  **stamps `raised_by = request.user`**; edit refused unless `obj.is_open`. Context `form`, `obj`,
  `invoice`, `is_edit`, `title`, `submit_label`, `cancel_url`.
- **`invoicedispute_delete`** — `@login_required @tenant_admin_required @require_POST` → `crud_delete`.
- **`invoicedispute_resolve`** — `@login_required @tenant_admin_required @require_POST`; POST keys
  `resolution` (required, must be in `RESOLUTION_CHOICES`) and `resolution_note` (optional); when
  `resolution == "credit_memo"` **and** `request.POST.get("spawn_credit_memo")` is truthy, create a
  `SupplierInvoice(invoice_type="credit_memo", …)` for the negative `disputed_amount` and call
  `obj.link_credit_memo(cm)`; `write_audit_log(... "update", {"action":"resolve"})`; redirect to detail.
- **`invoicedispute_escalate` / `_await_supplier` / `_await_internal` / `_close`** — `@require_POST`
  (`escalate` and `close` also `@tenant_admin_required`).
- **`invoicedispute_aging`** — standalone, URL `dispute-aging/`, name `invoicedispute_aging`, template
  `dispute_aging.html`. Context: `buckets` (list of dicts with keys **`key`, `label`, `rows`, `count`,
  `amount`**; `key` ∈ `{"overdue","0-7","8-14","15-30","31-60","60+","none"}`), `page_obj`, `today`,
  `stats` (keys **`open`, `overdue`, `due_7d`, `resolved_30d`**), `bucket_choices`.

URLs (literals before `<int:pk>`):
```
invoice-disputes/                     invoicedispute_list
invoice-disputes/add/                 invoicedispute_create
invoice-disputes/aging/               invoicedispute_aging
invoice-disputes/<int:pk>/            invoicedispute_detail
invoice-disputes/<int:pk>/edit/       invoicedispute_edit
invoice-disputes/<int:pk>/delete/     invoicedispute_delete
invoice-disputes/<int:pk>/resolve/    invoicedispute_resolve
invoice-disputes/<int:pk>/escalate/   invoicedispute_escalate
invoice-disputes/<int:pk>/await-supplier/  invoicedispute_await_supplier
invoice-disputes/<int:pk>/await-internal/  invoicedispute_await_internal
invoice-disputes/<int:pk>/close/      invoicedispute_close
```

## TEMPLATES (lane D)

`invoicedispute/list.html` — stat cards (amber `message-square-warning` open · red `alert-triangle`
overdue · red `trending-up` escalated · green `check-circle` resolved); filters (q, status,
reason_code, supplier, assigned_to, overdue checkbox); columns Number · Invoice · Supplier ·
Reason badge · Disputed amount · Status badge · Due · Age · Assignee · Actions.
`detail.html` — `<dl class="detail-grid">` + the full audit trail (raised_by/at, resolved_at,
resolution, resolution_note, credit memo link) + its `variances` + the resolve panel with the
resolution `<select>`, a note `<textarea>`, the `spawn_credit_memo` checkbox and the Escalate /
Await supplier / Await internal / Close POST buttons gated on `can_*`.
`form.html` — raise-or-edit.
`dispute_aging.html` — one card per `buckets` entry with `count` + `amount` in the header and a table
of `rows`.

---

# Template safety rules (restated hard — every one has shipped as a bug before)

1. **Badges:** only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`,
   `badge-slate` (`static/css/theme.css:286-291`). `badge-success` / `-warning` / `-danger` /
   `-purple` **do not exist** and render completely unstyled. Always end an `{% if %}` chain with
   `{% else %}{{ obj.get_<field>_display }}{% endif %}` and a `badge-slate` fallback.
2. **`stat-icon`:** only `blue`, `green`, `orange`, `purple`, `slate` (`theme.css:260-264`).
   (`red` also exists at `:265` but is NOT in the approved set — do not use it.)
3. **`.detail-label` / `.detail-value` DO NOT EXIST.** The real shape is
   `<dl class="detail-grid"><div class="detail-item"><dt>Label</dt><dd>Value</dd></div></dl>`.
4. **Never interpolate a user-typed value into `onclick="return confirm('…')"`** (L42). Use the
   system-assigned `{{ obj.number }}` (an `SIV-`/`DSP-` string) or an integer count. Escape any
   apostrophe inside a literal as `\'`.
5. **Pagination:** always `{% if page_obj.has_previous %}` / `{% if page_obj.has_next %}` — or just
   `{% include "partials/pagination.html" %}`, which already guards both. Never call
   `previous_page_number` / `next_page_number()` unconditionally. The partial itself is wrapped in
   `{% if page_obj.paginator.num_pages > 1 %}`, so it renders nothing on a single page.
6. **`{# … #}` is single-line ONLY.** Multi-line comments use `{% comment %}…{% endcomment %}`
   or the text leaks into the page as visible text.
7. **`{{ obj.fk.x|default:obj.fk.y }}` RAISES when `fk` is None.** Wrap every FK-derived expression in
   `{% if obj.fk %}…{% endif %}` — specifically `approved_by`, `assigned_to`, `raised_by`, `vendor`,
   `supplier`, `bill`, `journal_entry`, `document`, `payment_term`, `currency`.
8. `currency.code` is safe only inside `{% if obj.currency %}`; render `{{ obj.total }}` bare otherwise.
9. Templates extend `base.html` (blocks `title`, `content`, `extra_css`, `extra_js`). Lucide icons are
   `data-lucide="…"` on an `<i>`.

**Approved icon set (nothing outside it):** `file-text`, `file-input`, `file-up`, `upload`, `copy`,
`git-merge`, `scale`, `calendar-clock`, `percent`, `alert-triangle`, `alert-octagon`,
`message-square-warning`, `package`, `layers`, `receipt`, `wallet`, `trending-up`, `clock`, `eye`,
`pencil`, `trash-2`, `plus`, `search`, `check-circle`, `ban`, `refresh-cw`, `send`, `credit-card`,
`rotate-ccw`, `x-circle`, `clipboard-list`, `clipboard-x`.

---

# Integrator-only work (NOT a builder task)

`models/__init__.py` re-export all four models **and** every CHOICES tuple the templates use
(`STATUS_CHOICES`, `INVOICE_TYPE_CHOICES`, `MATCH_BASIS_CHOICES`, `MATCH_STATUS_CHOICES`,
`SOURCE_CHOICES`, `DISCOUNT_BASE_CHOICES`, `VARIANCE_TYPE_CHOICES`, `OUTCOME_CHOICES`,
`RESOLUTION_CHOICES`, `BASIS_CHOICES`, `REASON_CODE_CHOICES`) into `__all__` — surgical `Edit`, another
session may be in this tree.
`forms/__init__.py` and `views/__init__.py` re-export **every** new name (a missing view is an
`AttributeError` at URLconf import, not at request time).
`urls/__init__.py`: `from .InvoiceVoucherManagement import urlpatterns as _ivm_invoicevoucher`, splat
**LAST**, and extend the segment inventory in the docstring (lines 6-15).
`admin.py`: register `SupplierInvoice`, `InvoiceMatchVariance`, `InvoiceDispute`, with
`SupplierInvoiceLine` as an inline of `SupplierInvoice`; `readonly_fields` covers every `editable=False`
stamp.
`apps/core/navigation.py`: exactly ONE new `LIVE_LINKS["6.13"]` after `"6.12"` (ends at `:1593`),
bullet text copied verbatim from NavERP.md 1081-1085, with a comment recording that bullet 1 is
Assisted Capture, not OCR:
```
"Invoice Capture (OCR)":             "procurement:supplierinvoice_capture",
"Three-Way Matching":                "procurement:matchvariance_list",
"Dispute Resolution Workflow":       "procurement:invoicedispute_list",
"Payment Schedule/Terms Management": "procurement:paymentschedule_list",
"Early Payment Discount Tracking":   "procurement:discountopportunity_list",
```
Migration `0020` (latest on disk is `0019_returntovendor_prc_rtv_tnt_rma_idx.py`) — generated last,
renamed if Django picks another suffix.
`seed_procurement.py::_seed_invoice_voucher(tenant)` — existence-guard before every `.create()`,
`invoice_date` relative to `timezone.localdate() - timedelta(days=n)` (L16), no media files written.
`config/settings.py` / `config/urls.py` — **NO CHANGE**. `views/_helpers.py` — **do not touch**.

---

# Verification checklist (Integrator + smoke tester)

- [ ] `makemigrations procurement` → exactly **0020**; `migrate`; `manage.py check` clean; seeder runs twice clean.
- [ ] Every view renders 200/302 as `admin_acme`/`password`, **including unbound GET forms** (L39).
- [ ] **Blank-page proof:** every context key listed above asserted present and non-empty.
- [ ] Filters: each valid choice returns the right rows (positive path, L11/L44) AND
      `?status=nope&vendor=abc&variance_type=zzz&page=2` still 200s.
- [ ] Cross-tenant IDOR: an `admin_globex` invoice / variance / dispute pk returns **404** on
      detail/edit/delete and on every verb.
- [ ] Verbs reject GET (405); a non-admin is refused on approve / override / void / reverse /
      revalidate / resolve / delete (`@tenant_admin_required`, L27).
- [ ] **L42:** an invoice whose `invoice_number` contains an apostrophe deletes with the confirm
      dialog intact (the confirm string is the `SIV-` number).
- [ ] **L33:** grep the rendered HTML for `badge-success|badge-warning|badge-danger|badge-purple|
      detail-label|detail-value` → **zero** hits; no `{#` / `{% comment` leaking as text.
- [ ] **L40 §3:** matching an invoice to a PO and a GRN from a DIFFERENT vendor emits a `block`
      vendor-mismatch variance and does not advance.
- [ ] **L38:** with zero stock locations, a PO-less invoice and a no-receipt invoice both match and page.
- [ ] **L37 §2 / L29:** approving creates exactly ONE `accounting.Bill` and ONE **balanced**
      `JournalEntry` (debits == credits); approving TWICE creates no second entry; `reversed` posts a
      reversing entry and leaves the original untouched.
- [ ] `accounting.Bill` is the only ledger target — no write to `scm.GoodsReceiptNote.bill` from 6.13.
- [ ] Over-invoicing: 3 invoices of 40 against a PO of 100 are each within tolerance individually, but
      the 3rd blocks on the cumulative check.
- [ ] Credit memo: negative total, excluded from cumulative aggregation, never runs a 3-way match.
- [ ] Discount maths: `2/10 Net 30` ⇒ `annualised_pct == 36.73` (±0.01); only `approved`/`scheduled`
      rows with `amount_paid == 0` appear as capturable.
- [ ] Capture page: with `pdfplumber` absent, uploading a PDF drops to the manual form with
      `source="manual"` and `extraction_confidence=0`, and the page NEVER says "OCR".
- [ ] Tests derive dates from `timezone.localdate()` (L16); final proof run keeps migrations on and is
      UNFILTERED (L49).
- [ ] Sidebar shows 6.13 Live with all five bullets resolving — no `NoReverseMatch`.
