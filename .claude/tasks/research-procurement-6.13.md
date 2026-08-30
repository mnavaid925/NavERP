# Research — Sub-module 6.13: Invoice & Voucher Management (Module 6 — Procurement, app `procurement`)

Scope note: ONE sub-module, five NavERP.md bullets. The single most important finding of this research is that
**bullet 1 (Invoice Capture OCR) cannot be honestly delivered as OCR without external infrastructure**, and that
**bullets 4 and 5 (payment terms / early payment discounts) need no new model at all** — `accounting.PaymentTerm`
already carries `discount_pct` + `discount_days`, so both pages are pure derived views over `SupplierInvoice`.
Recommended build is therefore **4 models**, one of which is a variance register and one a dispute register.

---

## Repo state checked first

`6.1 · 6.2 · 6.3 · 6.4 · 6.5 · 6.6 · 6.7 · 6.8 · 6.9 · 6.10 · 6.11 · 6.12` are LIVE (`apps/core/navigation.py`);
**6.13 is the next unbuilt sub-module**.

Prefixes already taken in `procurement`: `ASN BID BKO CAM CMI CUB DSC EAUC EBID PCI PCO POE RAM RDS RFX RQA RQT
RTV RXR SEV VIS VPA VSU`. **`SIV` and `DSP` are free** (grep across `apps/` → no matches).

### Spine entities VERIFIED TO EXIST (grep evidence)

| Entity | Evidence | What it already does |
|---|---|---|
| `accounting.PaymentTerm` | `models/AccountsPayable/PaymentTerms.py:6` | **Has `days_due` (default 30), `discount_pct` (5,2), `discount_days`** — i.e. "2/10 Net 30" is ALREADY modelable. No `discount_base`, no grace days. |
| `accounting.Bill` / `BillLine` | `models/AccountsPayable/Bills.py:6,78` | `[BILL-]`, `party`, `payment_terms`, `bill_date`, `due_date`, `status` draft/pending_approval/approved/partial/paid/void, `currency`, `journal_entry`, subtotal/tax_total/total (editable=False), `document`→`core.Document`, `recalc_totals()`, `amount_paid()`, `balance_due()` |
| `scm.GoodsReceiptNote` | `models/ProcurementManagement/GoodsReceiptNotes.py:15` | `[GRN-]`, `bill`→`accounting.Bill`, `match_status` (not_matched/matched/price_variance/quantity_variance/over_received), `PRICE_TOLERANCE_PCT = 2`, `recompute_match()`, `received_value()` |
| `scm.GoodsReceiptLine` | `…/GoodsReceiptNotes.py:166` | `goods_receipt`, `po_line` (PROTECT), `quantity_received`, `quantity_rejected`, `rejection_reason`. **No item FK, no own tenant field.** |
| `scm.PurchaseOrderLine` | `…/PurchaseOrders.py:172` | FREE TEXT `item_description`/`sku_hint`/`uom_hint`; `quantity`, `unit_price`, `tax_rate_pct`, `line_total`, `gl_account`→`accounting.GLAccount`; `received_quantity()` / `outstanding_quantity()` |
| `procurement.VendorInvoiceSubmission` | `models/VendorManagement/VendorInvoiceSubmissions.py:16` | `[VIS-]`, supplier-portal-side, **HEADER ONLY** (`invoice_ref`, `invoice_date`, `amount`, no lines), status submitted/under_review/accepted/rejected. Docstring: *"the bill itself is keyed into Accounting › Accounts Payable afterwards."* |
| `procurement.ReceiptTolerancePolicy` | `models/GoodsReceiptInspection/ReceiptTolerances.py:51` | 6.12's tolerance resolver. Its own docstring says: *"wiring it into `recompute_match()` … is parked for 6.13."* |

**Division of labour this implies:** `VendorInvoiceSubmission` (6.4) = what the *supplier* claims.
`SupplierInvoice` (6.13) = what *AP* validated, matched, and is willing to pay. `accounting.Bill` = what the
*ledger* records. 6.13 is the bridge between the first two and the last.

---

## 1. Sources

| Product | URL |
|---|---|
| Oracle Fusion Payables — Invoice Tolerances | https://docs.oracle.com/en/cloud/saas/financials/25d/fappp/invoice-tolerances.html |
| Oracle NetSuite — Invoice Approval Workflow States | https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_4171578435.html |
| SAP — Invoice Tolerance Keys (T169G, MIRO/LIV) | https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-members/invoice-tolerance-keys-an-insight-part-1/ba-p/13085884 |
| SAP — Invoice Status (Logistics Invoice Verification) | https://help.sap.com/docs/SAP_S4HANA_CLOUD_PE/af9ef57f504840d2b81be8667206d485/f46fb6531de6b64ce10000000a174cb4.html |
| SAP Ariba — Credit Memos and Debit Memos | https://help.sap.com/docs/buying-invoicing/creating-and-managing-invoices/working-with-credit-memos-and-debit-memos |
| Coupa — Invoice Matching Explained (2/3/4-way) | https://www.coupa.com/blog/what-is-invoice-matching/ |
| Coupa — Invoice Management (tolerance levels) | https://www.coupa.com/products/ap-automation/invoicing/ |
| Microsoft Dynamics 365 — Vendor invoices overview | https://learn.microsoft.com/en-us/dynamics365/finance/accounts-payable/vendor-invoices-overview |
| Basware — Invoice Matching & Automation | https://www.basware.com/en/solutions/ap-automation/invoice-matching |
| HighRadius — Early Payment Discount | https://www.highradius.com/resources/Blog/early-payment-discount/ |
| AccountingTools — Cost of Credit Formula (annualised discount) | https://www.accountingtools.com/articles/cost-of-credit-formula |
| OATUG — Resolving Match Exception Invoice Holds in Oracle Fusion | https://www.oatug.org/insight-spring2025/features-archive/resolving-match-exceptions |
| Peakflo — Resolving Disputed Invoices in AP | https://blog.peakflo.co/en/account-payable/invoice-dispute-in-accounts-payable |
| Parseur — Extract Invoice Data from PDF with Python (OCR reality) | https://parseur.com/blog/extract-data-from-invoices-with-python |
| Subhajit Bhar — Invoice Data Extraction, Script to Production Pipeline | https://subhajitbhar.com/blog/idp/invoice-data-extraction-python |

Also consulted (secondary/SEO-grade, used only for corroboration): Medius AI, Tipalti, Stampli vs BILL vs
AvidXchange, Workday hold-reason admin guide, HighRadius invoice-matching software pages.

---

## 2. Deduplicated, prioritised feature catalog

| # | Feature | P | Bullet | Products doing it |
|---|---|---|---|---|
| F1 | Invoice header capture: vendor invoice no., date, due date, currency, gross/net/tax, PO ref | P0 | Capture | All |
| F2 | Invoice **line** capture (qty, unit price, amount, tax, GL coding) | P0 | Capture | SAP, Oracle, Coupa, D365, Basware |
| F3 | File attachment + retention of the source document | P0 | Capture | All (D365/SAP → `core.Document` equivalent) |
| F4 | **Duplicate invoice detection** (vendor + normalised invoice no. + amount + date window) | P0 | Capture | Coupa SpendGuard, Basware, D365 (`Reject duplicate`), HighRadius |
| F5 | Per-field **capture confidence** + human correction loop (the honest OCR stand-in) | P0 | Capture | Medius, Basware, Tipalti |
| F6 | **True OCR** on scanned/image PDFs | **P2 / external** | Capture | Basware, Medius, HighRadius, Tipalti — **all require an OCR engine or vision API** |
| F7 | Structured e-invoice ingest (UBL 2.1 / Factur-X / ZUGFeRD XML) | P2 | Capture | Basware, SAP, Ariba Network |
| F8 | Three-way match run: line-level qty vs received, price vs PO | P0 | 3-Way | All |
| F9 | Tolerance bands: price %, qty %, absolute amount, upper/lower, header total | P0 | 3-Way | Oracle (7 qty-based + 7 amount-based), SAP (T169G keys), Coupa |
| F10 | Variance register with type + expected/actual + verdict + auto-accept vs block | P0 | 3-Way | Oracle (holds), SAP (blocking reasons `SPGRP/M/Q/S/C`), Basware (root cause codes) |
| F11 | **2-way match** for service / PO-less invoices (no GRN) | P0 | 3-Way | Coupa ("service sheets"), SAP (no-GR item category), Oracle (Amount match basis) |
| F12 | **Partial receipt / partial invoicing** (cumulative invoiced vs cumulative received) | P0 | 3-Way | SAP tolerance keys `DQ`/`DW`, D365 ("match partial quantities for a line") |
| F13 | 4-way match (adds quality inspection) | P1 | 3-Way | Coupa, SAP (`SPGRC` quality block) — `scm.QualityInspection` exists |
| F14 | FX / conversion-rate tolerance | P1 | 3-Way | Oracle (`Conversion Rate Amount`, `Total Amount`) |
| F15 | Over-invoicing guard (cumulative invoiced > ordered, or > received + tol) | P0 | 3-Way | SAP `DQ`/`DW`, D365 (PO `Invoice remainder`) |
| F16 | Dispute register with **reason codes** and an auditable trail | P0 | Dispute | Peakflo, Stampli, Ariba, Workday (hold reasons) |
| F17 | Dispute **routing** to supplier + internal owner + SLA/due date | P0 | Dispute | Stampli, Peakflo, Workday |
| F18 | Dispute **resolution actions**: credit memo expected / debit memo / short-pay / re-invoice | P0 | Dispute | SAP Ariba (header+line credit memos, line-level debit memos) |
| F19 | Supplier-facing communication thread | P1 | Dispute | Stampli, Ariba, Basware |
| F20 | Credit memo as a negative invoice type (not a separate table) | P0 | Dispute | SAP (`Storno`/credit memo), Ariba, Oracle |
| F21 | Payment terms on the invoice (net days) + derived due date | P0 | Terms | `accounting.PaymentTerm` already |
| F22 | Early-payment discount: %, days, base, **grace days** | P0 | Terms | `PaymentTerm.discount_pct/discount_days` already; base+grace are NEW |
| F23 | Terms **override** per invoice / per vendor | P1 | Terms | Oracle (tolerance & terms assigned per supplier site) |
| F24 | **Payment schedule** — projected cash-out bucketed by due week | P0 | Terms | NetSuite, Tipalti, AvidXchange |
| F25 | **Discount opportunity dashboard** — discount date vs today, $ capturable, days left | P0 | Discount | HighRadius, Tipalti, Coupa |
| F26 | **Annualised value** of taking the discount (cost of credit) | P1 | Discount | AccountingTools standard; HighRadius/Tipalti expose it |
| F27 | Dynamic discounting (sliding scale, e.g. 2%/5d, 1.5%/10d, 1%/15d) | P2 | Discount | Coupa, Taulia, C2FO |
| F28 | Posting a balanced `JournalEntry` on approval, inside `transaction.atomic()` | P1 | Cross | Existing accounting pattern |

**P0 count:** 16. **Deliberately excluded from P0:** true OCR (F6), dynamic discounting (F27), supplier
communication thread (F19), 4-way match (F13), FX tolerance (F14).

---

## 3. Recommended build scope — 4 models

All under `apps/procurement/models/InvoiceVoucherManagement/`: `SupplierInvoices.py`,
`SupplierInvoiceLines.py`, `MatchVariances.py`, `InvoiceDisputes.py`.

### 3.1 `SupplierInvoice` (TenantNumbered, prefix `SIV`)

**Purpose:** the AP-side record of one supplier invoice — what the supplier billed, what we validated it
against, what we will pay, when, and at what discount. The state machine owner and the anchor for every
other table here.

```python
STATUS_CHOICES = [
    ("draft", "Draft"),                      # keyed, not yet validated
    ("parked", "Parked"),                    # SAP MIR7 — deliberately incomplete, excluded from matching
    ("captured", "Captured"),                # capture/import done, match not yet run
    ("blocked", "Blocked"),                  # Oracle "hold" / SAP block 'A' — variance outside tolerance
    ("disputed", "Disputed"),                # raised with the supplier
    ("pending_approval", "Pending Approval"),# matched, routed for approval (NetSuite Pending Approval)
    ("approved", "Approved"),                # cleared to pay
    ("scheduled", "Scheduled"),              # on a payment run
    ("paid", "Paid"),                        # terminal
    ("void", "Void"),                        # terminal — never posted
    ("reversed", "Reversed"),                # terminal — SAP storno of a posted invoice
]
INVOICE_TYPE_CHOICES = [
    ("standard", "Standard Invoice"),
    ("credit_memo", "Credit Memo"),
    ("debit_memo", "Debit Memo"),
    ("prepayment", "Prepayment / Down-payment Request"),
    ("service", "Service Invoice (PO-less)"),
]
MATCH_BASIS_CHOICES = [          # Oracle's quantity vs amount match-basis vocabulary
    ("quantity", "Quantity"),    # goods: 3-way against PO + GRN
    ("amount", "Amount"),        # services: 2-way against PO value only
    ("none", "No Match"),        # PO-less / non-PO coding
]
MATCH_STATUS_CHOICES = [
    ("not_run", "Not Run"),
    ("matched", "Matched"),
    ("within_tolerance", "Matched Within Tolerance"),
    ("price_variance", "Price Variance"),
    ("quantity_variance", "Quantity Variance"),
    ("total_variance", "Total Amount Variance"),
    ("fx_variance", "FX / Conversion-Rate Variance"),
    ("no_receipt", "No Receipt Posted"),
    ("over_invoiced", "Over-Invoiced"),
    ("duplicate_suspect", "Duplicate Suspect"),
]
SOURCE_CHOICES = [
    ("manual", "Manual Keying"),
    ("pdf_text_layer", "PDF Text-Layer Extraction"),
    ("e_invoice_xml", "Structured E-Invoice (XML)"),
    ("vis", "Vendor Portal Submission"),
    ("ocr", "OCR Engine"),          # reserved for the F6 external integration
]
DISCOUNT_BASE_CHOICES = [
    ("net_of_tax", "Net of Tax"),
    ("gross", "Gross (Incl. Tax)"),
]
```

| Field | Type | Points at | Notes |
|---|---|---|---|
| `tenant` | FK `core.Tenant` CASCADE | — | from `TenantOwned` (`related_name="+"`) |
| `number` | Char(20) | — | `SIV-00001`, from `TenantNumbered` |
| `vendor` | FK `core.Party` **PROTECT** | `core.Party` | `related_name="procurement_supplier_invoices"`. Vendor = a PartyRole, never a separate table. |
| `purchase_order` | FK `scm.PurchaseOrder` SET_NULL | `scm.PurchaseOrder` | null ⇒ PO-less/service. `related_name="procurement_supplier_invoices"` |
| `goods_receipt` | FK `scm.GoodsReceiptNote` SET_NULL | `scm.GoodsReceiptNote` | the receipt this was matched to (one invoice may span several GRNs — if so, leave null and link per line) |
| `bill` | FK `accounting.Bill` SET_NULL | `accounting.Bill` | **the ledger record created on approval.** `related_name="procurement_supplier_invoices"`. 6.13 writes this ONCE, at `approved`. |
| `journal_entry` | FK `accounting.JournalEntry` SET_NULL | `accounting.JournalEntry` | balanced entry posted inside `transaction.atomic()`; `editable=False` |
| `payment_term` | FK `accounting.PaymentTerm` SET_NULL | `accounting.PaymentTerm` | supplies `days_due`, `discount_pct`, `discount_days` |
| `currency` | FK `accounting.Currency` SET_NULL | `accounting.Currency` | invoice currency; FX variance compares it to the PO currency |
| `tax_code` | FK `accounting.TaxCode` SET_NULL | `accounting.TaxCode` | header default, overridable per line |
| `source_submission` | FK `procurement.VendorInvoiceSubmission` SET_NULL | 6.4's VIS | bridges supplier-filed → AP-validated; null when keyed in-house |
| `document` | FK `core.Document` SET_NULL | `core.Document` | the uploaded PDF/image (F3) |
| `invoice_type` | Char(20) | — | `INVOICE_TYPE_CHOICES`; credit/debit memo is a TYPE, not a table |
| `invoice_number` | Char(64) | — | the SUPPLIER's number. **Duplicate detection key.** |
| `invoice_number_norm` | Char(64), `editable=False`, db_index | — | uppercased, stripped of non-alphanumerics — catches `INV-100` vs `INV100` |
| `external_ref` | Char(64) blank | — | supplier's delivery note / contract ref |
| `invoice_date` | DateField | — | drives discount date + due date |
| `posting_date` | DateField null | — | date hitting the ledger; defaults to approval date |
| `due_date` | DateField null, `editable=False` | — | derived: `invoice_date + payment_term.days_due` |
| `discount_date` | DateField null, `editable=False` | — | derived: `invoice_date + payment_term.discount_days` |
| `discount_expiry_date` | DateField null, `editable=False` | — | `discount_date + grace_days` |
| `discount_base` | Char(10) | — | `DISCOUNT_BASE_CHOICES`, default `net_of_tax` |
| `discount_grace_days` | PosSmallInt default 0 | — | days after `discount_date` the discount is still honoured |
| `subtotal` | Decimal(18,2) `editable=False` | — | derived by aggregation from lines |
| `tax_total`, `total` | Decimal(18,2) `editable=False` | — | derived, never editable (L29) |
| `amount_paid` | Decimal(18,2) `editable=False` | — | derived from `accounting.Payment` allocations against `bill` |
| `fx_rate` | Decimal(14,6) null | — | invoice currency → ledger currency, snapshot at capture |
| `match_basis` | Char(10) | — | `MATCH_BASIS_CHOICES`, auto-set from `purchase_order`/`goods_receipt` presence |
| `match_status` | Char(20) `editable=False` | — | `MATCH_STATUS_CHOICES`, set by `run_match()` |
| `match_notes` | TextField blank `editable=False` | — | mirrors `GoodsReceiptNote.match_notes` |
| `status` | Char(20) | — | `STATUS_CHOICES`, default `draft` |
| `source` | Char(20) | — | `SOURCE_CHOICES`, default `manual` |
| `extraction_confidence` | Decimal(5,2) null | — | 0–100, from the capture step (F5) |
| `extraction_raw_text` | TextField blank | — | retained for re-parsing and audit |
| `duplicate_of` | FK `self` SET_NULL | — | set when F4 fires |
| `approved_by` | FK `AUTH_USER_MODEL` SET_NULL `editable=False` | — | |
| `approved_at` | DateTime null `editable=False` | — | |
| `notes` | TextField blank | — | |

`class Meta`: `ordering = ["-invoice_date", "-id"]`, `unique_together = ("tenant", "number")`, plus indexes
`["tenant","status"]`, `["tenant","match_status"]`, `["tenant","vendor","invoice_number_norm"]` (the duplicate
index), `["tenant","discount_date"]` (the dashboard's hot query).

### 3.2 `SupplierInvoiceLine` (plain child, scoped through the header — same idiom as `GoodsReceiptLine`)

**Purpose:** one billed line, and the join point where invoice ↔ PO line ↔ receipt line are compared.

| Field | Type | Points at |
|---|---|---|
| `invoice` | FK `SupplierInvoice` CASCADE `related_name="lines"` | — |
| `po_line` | FK `scm.PurchaseOrderLine` PROTECT null `related_name="procurement_invoice_lines"` | expected qty/price |
| `receipt_line` | FK `scm.GoodsReceiptLine` PROTECT null `related_name="procurement_invoice_lines"` | actually received qty |
| `description` | Char(255) | free-text fallback for non-PO lines |
| `sku_hint`, `uom_hint` | Char(64)/Char(32) blank | matches the PO-line idiom |
| `quantity` | Decimal(14,4) default 1 | billed qty |
| `unit_price` | Decimal(14,2) default 0 | billed price |
| `tax_rate_pct` | Decimal(5,2) default 0 | |
| `line_total` | Decimal(18,2) `editable=False` | derived in `save()` |
| `gl_account` | FK `accounting.GLAccount` SET_NULL `related_name="procurement_invoice_lines"` | non-PO coding (Basware "automated coding") |
| `tax_code` | FK `accounting.TaxCode` SET_NULL null | line override |
| `cumulative_invoiced_qty` | Decimal(14,4) `editable=False` | **derived**, NOT stored: sum of this line's qty across all non-terminal invoices for the same `po_line` |
| `matched_qty` | Decimal(14,4) `editable=False` | filled by `run_match()` = quantity accepted against receipts |

`save()` recomputes `line_total`; the header then calls `recalc_totals()` (mirrors `Bill.recalc_totals`).

### 3.3 `InvoiceMatchVariance` (TenantOwned — no number; nobody quotes a variance by reference)

**Purpose:** the exception register. One row per failed/near-miss check. This is what makes the
"three-way match exceptions board" a page instead of a log message, and it is what a dispute is raised from.

```python
VARIANCE_TYPE_CHOICES = [
    ("price", "Unit Price"),
    ("quantity", "Quantity vs Receipt"),
    ("quantity_no_receipt", "Quantity vs Order (No Receipt)"),
    ("over_invoice", "Cumulative Over-Invoicing"),
    ("total_amount", "Header Total"),
    ("fx_rate", "FX / Conversion Rate"),
    ("tax", "Tax Amount"),
    ("duplicate", "Duplicate Invoice"),
    ("missing_po", "No PO Reference"),
    ("missing_receipt", "No Goods Receipt"),
]
OUTCOME_CHOICES = [
    ("auto_accept", "Auto-Accepted (Within Tolerance)"),
    ("warn", "Accepted With Warning"),
    ("block", "Blocked — Outside Tolerance"),
]
RESOLUTION_CHOICES = [
    ("open", "Open"),
    ("accepted", "Accepted by AP"),
    ("disputed", "Disputed With Supplier"),
    ("credit_memo", "Resolved by Credit Memo"),
    ("debit_memo", "Resolved by Debit Memo"),
    ("short_paid", "Resolved by Short Payment"),
    ("cancelled", "Cancelled"),
]
```

| Field | Type | Points at |
|---|---|---|
| `tenant` | FK `core.Tenant` | from base |
| `invoice` | FK `SupplierInvoice` CASCADE `related_name="variances"` | |
| `invoice_line` | FK `SupplierInvoiceLine` CASCADE null `related_name="variances"` | null ⇒ header-level check |
| `variance_type` | Char(20) | `VARIANCE_TYPE_CHOICES` |
| `basis` | Char(20) | `po` / `receipt` / `header` — what "expected" was measured against |
| `expected_value` | Decimal(18,4) | |
| `actual_value` | Decimal(18,4) | |
| `variance_abs` | Decimal(18,4) `editable=False` | signed: actual − expected |
| `variance_pct` | Decimal(9,4) `editable=False` | signed % |
| `tolerance_abs_applied` | Decimal(18,4) null | the band that was actually used |
| `tolerance_pct_applied` | Decimal(9,4) null | |
| `outcome` | Char(12) | `OUTCOME_CHOICES` |
| `resolution` | Char(12) default `open` | `RESOLUTION_CHOICES` |
| `dispute` | FK `InvoiceDispute` SET_NULL null `related_name="variances"` | |
| `message` | Char(255) | human-readable root cause (Basware's "root cause error description") |
| `detected_at` | DateTime `auto_now_add` | |

### 3.4 `InvoiceDispute` (TenantNumbered, prefix `DSP`)

**Purpose:** the audit trail of "we told the supplier this invoice is wrong". Numbered because AP quotes the
reference in correspondence. Modelled on SAP Ariba (header- and line-level credit memos, line-level debit
memos) and Workday's configurable hold reasons.

```python
REASON_CODE_CHOICES = [
    ("price", "Price Dispute"),
    ("quantity", "Quantity Dispute"),
    ("goods_not_received", "Missing Goods"),
    ("damaged", "Damaged / Quality"),
    ("duplicate", "Duplicate Invoice"),
    ("credit_not_processed", "Credit Not Processed"),
    ("tax", "Tax / VAT Error"),
    ("freight", "Unapproved Freight or Charges"),
    ("admin", "Administrative Error"),
    ("other", "Other"),
]
RESOLUTION_CHOICES = [
    ("credit_memo", "Supplier Credit Memo"),
    ("debit_memo", "Debit Memo Raised"),
    ("reinvoice", "Supplier Re-Invoice"),
    ("short_pay", "Short Payment Accepted"),
    ("withdrawn", "Dispute Withdrawn"),
]
STATUS_CHOICES = [
    ("open", "Open"),
    ("awaiting_supplier", "Awaiting Supplier"),
    ("awaiting_internal", "Awaiting Internal Review"),
    ("resolved", "Resolved"),
    ("escalated", "Escalated"),
    ("closed", "Closed"),
]
```

| Field | Type | Points at |
|---|---|---|
| `invoice` | FK `SupplierInvoice` CASCADE `related_name="disputes"` | |
| `invoice_line` | FK `SupplierInvoiceLine` SET_NULL null `related_name="disputes"` | line-level disputes (Ariba allows line-level) |
| `supplier` | FK `core.Party` PROTECT `related_name="procurement_invoice_disputes"` | denormalised from the invoice for the vendor-facing queue |
| `reason_code` | Char(24) | `REASON_CODE_CHOICES` |
| `status` | Char(20) default `open` | `STATUS_CHOICES` |
| `disputed_amount` | Decimal(14,2) | the portion in dispute — drives "pay the undisputed balance now" |
| `description` | TextField | |
| `raised_by` | FK `AUTH_USER_MODEL` SET_NULL `editable=False` | |
| `assigned_to` | FK `AUTH_USER_MODEL` SET_NULL null | |
| `supplier_contact` | Char(120) blank | |
| `raised_at` | DateTime `auto_now_add` | |
| `due_date` | DateField null | SLA target (Peakflo: contact vendor within ~10 days) |
| `resolved_at` | DateTime null `editable=False` | |
| `resolution` | Char(16) blank | `RESOLUTION_CHOICES` |
| `resolution_note` | TextField blank | |
| `credit_memo_invoice` | FK `SupplierInvoice` SET_NULL null `related_name="resolved_disputes"` | the `invoice_type="credit_memo"` row that settled it |

### 3.5 Deliberately EXCLUDED, and why

| Not built | Why |
|---|---|
| **`InvoiceMatchTolerancePolicy` table** | 6.12 already proved the resolver pattern with `ReceiptTolerancePolicy`, but a second one doubles the config surface for one sub-module. Tolerances ship as **class constants on `SupplierInvoice`** (exactly the `GoodsReceiptNote.PRICE_TOLERANCE_PCT = 2` idiom already in the repo). Promoting them to a tenant-configurable table is P2 and needs no schema change to the four models. |
| **A separate `CreditMemo` / `DebitMemo` model** | SAP Ariba and Oracle both treat these as **invoice types**, not tables. `invoice_type` on `SupplierInvoice` with sign-aware totals gets the same result with one table. A separate model would fork every total, match, and dispute calculation. |
| **A stored `PaymentSchedule` table** | It is a projection: `SupplierInvoice` filtered to `approved`, bucketed by `due_date`. Storing it guarantees drift. Derived by aggregation (L29). |
| **A stored `DiscountOpportunity` table** | Same argument, stronger: it is a function of (today, `discount_date`, `total`, `discount_pct`). Storing it makes the page wrong the next morning. |
| **An OCR job/queue model** | No OCR engine exists in this stack. A job table with no worker is dead schema. See §5 and §9. |
| **A tolerance/terms-per-vendor table** | Oracle assigns tolerances per supplier *site*; that is a `core.Party` concern and a cross-app write. P1 at earliest. |
| **Supplier-facing portal pages** | 6.4 owns `VendorInvoiceSubmission` and the vendor portal. 6.13 records the dispute; it does not give suppliers a login. |

---

## 4. Status lifecycle — `SupplierInvoice.status`

```
                 ┌──────────────────────────────┐
                 │                              │
  draft ──► parked ──► captured ──► (run_match) ─┤
    │                                            │
    │                        within tolerance ───┼──► pending_approval ──► approved ──► scheduled ──► paid
    │                                            │          │                  │            │
    │                        outside tolerance ──┼──► blocked                  │            │
    │                                            │        │                    │            │
    │                        duplicate suspect ──┴──► blocked ◄────────────────┤            │
    │                                                   │                      │            │
    │                                                   ├──► disputed ──► (resolved) ──┘     │
    │                                                   │        │                            │
    │                                                   │        └──► credit_memo (new SIV)   │
    │                                                   │                                     │
    └──► void (never posted)                            └──► void                    reversed ◄┘
```

**Allowed transitions (enforce in the view, not the model):**

| From | To | Guard |
|---|---|---|
| `draft` | `parked` / `captured` | — |
| `parked` | `draft` / `captured` | — |
| `captured` | `blocked` / `pending_approval` | set by `run_match()` |
| `blocked` | `pending_approval` | authorised override only (SAP's `M_RECH_AKZ` "Accept and Post"); writes an `accepted` variance resolution |
| `blocked` | `disputed` | at least one open variance must exist |
| `disputed` | `blocked` / `pending_approval` / `void` | |
| `pending_approval` | `approved` | `approved_by` + `approved_at` set; **this is the only transition that writes `accounting.Bill` + `JournalEntry`** |
| `pending_approval` | `blocked` | approver sends back |
| `approved` | `scheduled` / `void` / `reversed` | |
| `scheduled` | `paid` / `approved` | returning to `approved` = payment run rejected |
| `paid` | `reversed` | creates the reversing `JournalEntry`; never edits the original (append-only ledger) |
| any non-terminal | `void` | |

`is_locked` ⇔ status in `("paid", "void", "reversed")` — mirrors `Bill.is_locked`.

---

## 5. Tolerance & matching rules

### 5.1 Recommended numeric defaults

Ship as class constants on `SupplierInvoice` (repo idiom: `GoodsReceiptNote.PRICE_TOLERANCE_PCT`). **Where
both a % and an absolute band are set, the MORE RESTRICTIVE wins** — the rule 6.12's
`ReceiptTolerancePolicy` already applies, and Oracle's `Maximum Ordered` / `Maximum Received` behave the same.

| Constant | Default | Applies to | Rationale / source |
|---|---|---|---|
| `PRICE_TOL_PCT_UPPER` | **2.00 %** | `invoice_line.unit_price` vs `po_line.unit_price` | Matches `GoodsReceiptNote.PRICE_TOLERANCE_PCT = 2` already in the repo |
| `PRICE_TOL_PCT_LOWER` | **None** (no floor) | ditto | Under-billing is not a risk. SAP models these as independent lower limits; Oracle's default is "no value ⇒ infinite variance" |
| `PRICE_TOL_ABS_UPPER` | **50.00** (ledger ccy) | ditto | SAP tolerance key `AP` (absolute item amount). Use when POs share a value band |
| `QTY_TOL_PCT_UPPER` | **0.00 %** | invoiced qty vs **received** qty | Strict: never pay for more than arrived. SAP `DQ` treats an unmaintained tolerance as ZERO and blocks any deviation |
| `QTY_TOL_ABS_UPPER` | **0.0000** | ditto | same posture, absolute form |
| `QTY_TOL_PCT_UPPER_NO_GRN` | **5.00 %** | invoiced qty vs **ordered** qty when no receipt exists | SAP tolerance key `DW` (GR qty = 0), Oracle `Ordered Percentage` |
| `QTY_TOL_PCT_LOWER` | **5.00 %** | invoiced qty vs ordered | Short-invoicing a line that is still open is normal (partial invoicing) |
| `TOTAL_TOL_PCT` | **1.00 %** | header `total` vs Σ expected | Oracle `Total Amount` |
| `TOTAL_TOL_ABS` | **25.00** (ledger ccy) | ditto | SAP tolerance key `BD` — "small differences", auto-posted to a DIF account when inside the band |
| `FX_TOL_PCT` | **1.00 %** | ledger-currency total vs PO converted total | Oracle `Conversion Rate Amount` |
| `TAX_TOL_ABS` | **1.00** (ledger ccy) | Σ line tax vs header `tax_total` | Rounding only, not a tax-policy check |
| `DATE_TOL_DAYS` | **5** | `invoice_date` vs latest `receipt_date` | SAP tolerance key `SPGRT` (date block). Guards back-dated invoices |
| `DUPLICATE_WINDOW_DAYS` | **90** | duplicate scan lookback | D365 checks against posted invoices; 90 days covers the common re-send cycle |
| `DISCOUNT_GRACE_DAYS` | **0** | `discount_expiry_date` | Conservative default. Vendors routinely honour 1–3 days; expose per invoice |

### 5.2 The match algorithm (`SupplierInvoice.run_match()`)

Per line, in this order — first breach wins, because it is the one somebody has to chase (6.12's
`evaluate_receipt_tolerance` uses the same "quantity outranks date" ordering):

1. **`missing_po`** — `match_basis != none` and no `po_line` → `block`.
2. **`missing_receipt`** — basis is `quantity`, no `receipt_line` → compare against **ordered** using
   `QTY_TOL_PCT_UPPER_NO_GRN`. (SAP `DW`.)
3. **`quantity`** — compare `quantity` against `receipt_line.quantity_received`, and compare
   `cumulative_invoiced_qty` against `cumulative_received_qty` for that `po_line`. SAP `DQ`:
   `variance = PO price × (qty invoiced − (total delivered − total already invoiced))`.
4. **`over_invoice`** — `cumulative_invoiced_qty > po_line.quantity + allowance` → `block`. (D365 blocks when
   invoice qty exceeds the PO invoice remainder.)
5. **`price`** — `unit_price` vs `po_line.unit_price`, upper/lower bands as above.
6. Header: **`total_amount`**, **`fx_rate`** (only if `currency` ≠ PO currency), **`tax`**.
7. **`duplicate`** — see §8.

Outcome mapping: every variance inside its band → `auto_accept` and the invoice advances to
`pending_approval` (NetSuite: "Transactions without any exceptions are automatically approved"). Any
`block` → status `blocked` and the invoice appears on the exceptions board. `warn` → advances but is listed.

**Partial receipts / partial invoicing:** `cumulative_invoiced_qty` and `cumulative_received_qty` are
aggregations across **all non-terminal invoices and all `status="received"` GRNs** for the same `po_line`.
This is the single most important correctness property in the whole sub-module — see §9.

**PO-less / service invoices:** `match_basis="amount"` skips steps 2–4 entirely and compares only the value
against the PO (Coupa's service-sheet behaviour, Oracle's Amount match basis). `match_basis="none"` skips
matching and requires a `gl_account` on every line (Basware's "automated coding of non-PO backed invoices").

### 5.3 Early-payment discount maths (F25/F26)

```
discount_date        = invoice_date + payment_term.discount_days
due_date             = invoice_date + payment_term.days_due
discount_expiry_date = discount_date + discount_grace_days
discount_base_amount = (discount_base == "net_of_tax") ? subtotal : total
discount_amount      = discount_base_amount × payment_term.discount_pct / 100
payable_if_discounted= total − discount_amount
days_to_discount     = discount_expiry_date − today
capturable           = (days_to_discount >= 0) AND (status in approved/scheduled) AND (amount_paid == 0)

# Annualised value of taking the discount (AccountingTools cost-of-credit formula):
annualised_pct = discount_pct / (100 − discount_pct) × (360 / (days_due − discount_days))
# 2/10 Net 30 → 2/98 × 360/20 = 36.7%.  Use 360 for finance convention; make it a constant
# DISCOUNT_ANNUALISATION_DAYS = 360 so a 365 convention is a one-line change.
```

Sort the dashboard by `annualised_pct` DESC then `discount_amount` DESC — that surfaces the highest-value
decisions first, which is the entire point of the page.

---

## 6. Pages / routes

Namespace `procurement`. Package layout: `apps/procurement/urls/InvoiceVoucherManagement/*.py`,
`views/InvoiceVoucherManagement/*.py`, templates at `templates/procurement/InvoiceVoucherManagement/<entity>/*.html`.

**Bullet 1 — Invoice Capture (OCR)**
- `procurement:supplierinvoice_list` — register, filterable by status / match_status / vendor
- `procurement:supplierinvoice_detail` — header + lines + variances + disputes + attachments
- `procurement:supplierinvoice_create`, `procurement:supplierinvoice_update`, `procurement:supplierinvoice_delete`
- `procurement:supplierinvoice_capture` — **upload → extract → review-with-confidence → confirm** (the F5 flow)
- `procurement:supplierinvoice_duplicates` — duplicate-suspect workbench (F4)

**Bullet 2 — Three-Way Matching**
- `procurement:matchvariance_list` — the exceptions board (filter by `variance_type` / `outcome` / `resolution`)
- `procurement:matchvariance_detail`
- `procurement:supplierinvoice_match` — POST-only: run/re-run `run_match()` for one invoice
- `procurement:supplierinvoice_revalidate` — POST-only: re-run matching for everything in `blocked`/`captured`

**Bullet 3 — Dispute Resolution Workflow**
- `procurement:invoicedispute_list`, `procurement:invoicedispute_detail`
- `procurement:invoicedispute_create`, `procurement:invoicedispute_update`
- `procurement:invoicedispute_resolve` — POST: apply `RESOLUTION_CHOICES`, optionally spawn the credit memo
- `procurement:invoicedispute_aging` — open disputes by `due_date` bucket (the SLA view)

**Bullet 4 — Payment Schedule / Terms Management**
- `procurement:paymentschedule_list` — approved invoices bucketed by due week, with the term profile column

**Bullet 5 — Early Payment Discount Tracking**
- `procurement:discountopportunity_list` — the dashboard: `days_to_discount`, `discount_amount`,
  `annualised_pct`, sorted by annualised value

Supporting: `procurement:invoicevoucher_dashboard` — one sidebar entry (6.13) with tiles into all five.

Every view: `@login_required`, `Model.objects.filter(tenant=request.tenant)` (or
`filter(invoice__tenant=...)` for the child tables), never `.all()`.

---

## 7. Seeder plan

Minimum for the pages to look real (one demo tenant):

| Entity | Rows | Shape |
|---|---|---|
| `accounting.PaymentTerm` | 5 | `Net 30` (30/0/0), `Net 60` (60/0/0), `2/10 Net 30` (30/2.00/10), `1/15 Net 45` (45/1.00/15), `3/7 Net 60` (60/3.00/7) |
| `scm.PurchaseOrder` + lines | 6 | Across 4 vendors; at least 2 with multiple lines so partial matching is visible |
| `scm.GoodsReceiptNote` + lines | 8 | **Deliberately uneven:** 1 full receipt, 1 partial (60%), 1 partial then completed (two GRNs against one PO), 1 over-receipt (110), 1 with `quantity_rejected > 0`, 2 POs with **no receipt** (service invoices) |
| `SupplierInvoice` | 14 | Status mix must cover **every** state: 1 draft, 1 parked, 2 captured, 2 blocked, 2 disputed, 2 pending_approval, 2 approved, 1 scheduled, 1 paid. Include 1 `credit_memo` (negative total) resolving a dispute, 1 `debit_memo`, 2 `service` (PO-less, `match_basis="amount"`), 1 `source="pdf_text_layer"` with `extraction_confidence=87.50`, 1 with `duplicate_of` set |
| `SupplierInvoiceLine` | ~38 | 1–4 per invoice; non-PO lines carry a `gl_account` |
| `InvoiceMatchVariance` | ~16 | At least one of EACH `variance_type`; outcomes mixed `auto_accept` / `warn` / `block`; resolutions mixed, incl. 3 `credit_memo` |
| `InvoiceDispute` | 6 | One per distinct `reason_code` except `other`; 2 `open` past `due_date` (to light up the aging view), 1 `awaiting_supplier`, 1 `escalated`, 2 `resolved` |
| `core.Document` | 14 | One attachment per invoice (placeholder PDFs) so the detail page's download link works |
| `accounting.Bill` | 2 | Only for the `paid` and one `approved` invoice, so the "bridge to the ledger" is demonstrable |

Seed the `invoice_date`s **relative to today** (`today − n`), not hardcoded — otherwise the discount dashboard
shows zero opportunities the moment the demo ages.

---

## 8. Risks / gotchas

1. **Duplicate invoice detection is the highest-value control and the easiest to get wrong.** Exact match on
   `(vendor, invoice_number)` catches almost nothing: `INV-1001` / `INV 1001` / `inv1001` / `INV-1001-A` are the
   same invoice. Normalise to `invoice_number_norm` (uppercase, strip non-alphanumerics) and score on a
   weighted triple: normalised number (exact) + amount (±1%) + date (±`DUPLICATE_WINDOW_DAYS`). Flag as
   **`duplicate_suspect`**, never auto-reject — a legitimate re-invoice after a credit memo trips every
   heuristic. D365 lets you choose `Reject duplicate` vs warn; choose warn.
2. **Tax / rounding drift.** AP computes tax per line and sums; the supplier computes it on the invoice total.
   A 3-line invoice can be off by 2 cents and still be correct. Always compare tax with an absolute band
   (`TAX_TOL_ABS`), never a percentage, and never block an invoice on tax rounding alone. Worse: mixing
   tax-inclusive and tax-exclusive `unit_price` across lines silently inflates `total`. Store one convention
   and validate it in `clean()`.
3. **FX.** Never compare an invoice total to a PO total in different currencies. Convert the PO line price at
   the PO's rate, the invoice at `fx_rate`, and compare in **ledger** currency (Oracle `Conversion Rate
   Amount` does exactly this). Snap `fx_rate` at capture — a rate that moves between capture and approval
   produces a variance nobody can explain a month later.
4. **Partial receipt matching is where most home-grown implementations break.** The comparison is NOT
   invoice-qty vs one-GRN-qty. It is:
   `cumulative invoiced (all non-terminal invoices for this po_line)` vs
   `cumulative received (all status="received" GRNs for this po_line)`.
   Derive both by aggregation every time. Any cached counter will drift the first time a GRN is cancelled or
   an invoice reversed. This is SAP tolerance key `DQ`'s exact formula and the reason SAP can auto-release the
   block when the balance is later received.
5. **Over-invoicing across multiple invoices** is the classic leak: three invoices of 40 against a PO of 100,
   each within tolerance individually. The per-line cumulative check (§5.2 step 4) is the only defence. Add a
   DB index on `["tenant", "po_line"]` for it.
6. **Credit memos.** Model them as `invoice_type="credit_memo"` with a **negative** `total`, and exclude
   terminal-status rows from every cumulative aggregation. Forgetting the exclusion makes a credit memo look
   like additional spend. Also never let a credit memo run a normal three-way match — it has no receipts.
7. **Blocked invoices must still be payable in part.** Peakflo's guidance — pay the undisputed balance now —
   only works if `disputed_amount` is tracked separately from `total`. Otherwise a dispute freezes the whole
   invoice and the supplier stops shipping.
8. **Discount-date arithmetic vs business calendars.** `discount_date` falling on a weekend or holiday is
   routinely still honoured by suppliers but will read as "expired" in code. `DISCOUNT_GRACE_DAYS` is the
   cheap fix; a business-calendar-aware calc is P2. Do not hardcode 30-day months.
9. **The discount dashboard lies if it counts blocked invoices.** An invoice in `blocked` or `disputed` cannot
   be paid early, so its discount is not "opportunity" — it is noise. Filter to
   `status in ("approved","scheduled") AND amount_paid == 0`.
10. **Posting the `JournalEntry` twice.** Approval is the ONE transition that writes the ledger, and it will be
    retried (double-click, back button, re-approval after edit). Guard with
    `if invoice.journal_entry_id: return` inside `transaction.atomic()`, and make the discount posting explicit:
    Debit AP control, Credit Cash, Debit/Credit a Purchase-Discounts-Received account — the entry must balance
    whether or not a discount was taken.
11. **The `accounting.Bill` bridge is one-way.** `scm.GoodsReceiptNote.bill` already exists and 6.12 writes it.
    6.13 sets `SupplierInvoice.bill` on approval. Do **not** also write `GRN.bill` from here — two writers to
    one field, and 6.12's `recompute_match()` will fight it.
12. **`VendorInvoiceSubmission` (6.4) is header-only and has no lines.** Resist the urge to make 6.13 "fix" it.
    `source_submission` is a one-way reference; lines get keyed on the 6.13 side.

---

## 9. What is achievable WITHOUT an OCR engine (bullet 1, honestly)

**Not achievable:** anything involving a scanned or image-only PDF. `pdfplumber` / `PyMuPDF` read the PDF's
**text layer**; a scan has none and returns `None`. Every commercial product in §1 that claims OCR is running
Tesseract, a cloud OCR API, or a vision model behind it.

**Achievable, and worth building (P0): Assisted Capture.**

1. Upload the file to `core.Document`.
2. Try the text layer (`pdfplumber.extract_text()`). If `None` → `source="manual"`, `extraction_confidence=0`,
   and drop straight to the manual form. **This is the honest behaviour, not a failure path.**
3. Run anchor + regex heuristics for header fields (invoice no., date, due date, total, tax, PO number) and
   `extract_tables()` for line items.
4. Render the **normal create form pre-filled**, each extracted field badged with a confidence level, every
   field still editable.
5. On save, persist `source`, `extraction_confidence`, and `extraction_raw_text`.

Expectations to set honestly: `extract_table()` returns `None` on most real supplier invoices because columns
are whitespace-aligned with no ruling lines; regex anchored to `"Invoice Number:"` breaks the first time a
supplier re-templates; multi-page line items and merged cells defeat naive extraction. Rules-based extraction
handles roughly 70–80% of invoices from a *consistent* supplier base and much less from a heterogeneous one.
That is a genuine productivity win over manual keying — it is not OCR, and it should not be labelled as such
in the UI. Call the page **"Capture Invoice"**, not "OCR".

**P2, if external infrastructure is ever approved:** UBL 2.1 / Factur-X / ZUGFeRD XML ingest (deterministic,
near-100% accuracy, no model) is a far better investment than OCR for any supplier that can emit it. OCR
proper (Tesseract, or a vision API call from a Celery task) is the last option, not the first.
