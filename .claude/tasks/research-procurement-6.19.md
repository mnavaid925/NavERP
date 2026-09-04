# Research — Sub-module 6.19: Document & Knowledge Management (Module 6 — Procurement Management System, `procurement`)

> **Read this first.** 6.19 is the **procurement document & knowledge layer** — the shelf that every other 6.x
> sub-module puts its paperwork on. It is **not** an enterprise DMS (Module 13 owns that), it is **not** contract
> lifecycle management (6.8 already shipped that on `scm.SupplierContract`), and it is **not** a second attachment
> mechanism for invoices (6.13 already uses `core.Document`). The failure mode for this pass is **building Module
> 13 early**: folder trees, permission matrices, DRM/watermarking, OCR, semantic search and check-in/check-out
> branching are all real features in the products surveyed and all of them are explicitly Module 13's. What 6.19
> owns is a **procurement-scoped repository with real revision control, a policy library, a template/best-practice
> library, and in-process text search** — four models, full CRUD, nothing that needs infrastructure NavERP does not
> have.

---

## Repo state checked first

### LIVE_LINKS built so far in Module 6 (`apps/core/navigation.py`)

`6.1 · 6.2 · 6.3 · 6.4 · 6.5 · 6.6 · 6.7 · 6.8 · 6.9 · 6.10 · 6.11 · 6.12 · 6.13 · 6.14 · 6.15`
(last block is `"6.15"` at `navigation.py:1626`). **There is no `"6.16"`, `"6.17"`, `"6.18"` or `"6.19"` key** —
6.19 is being built ahead of 6.16–6.18, which matters for one boundary call (see *Belongs to sibling sub-modules*).

### Spine entities VERIFIED to exist (grep evidence — L28: the ERD is intent, the grep is truth)

| Entity | Verified at | What 6.19 uses it for |
|---|---|---|
| `core.Document` | `apps/core/models/Document.py:5` | the **generic** attachment (GFK + `file` + `classification` + flat `version` CharField). Already has CRUD at `core:document_*` and is FK'd live by `procurement.SupplierInvoice.document` (`SupplierInvoices.py:289`). **6.19 does not extend or replace it** — see the ruling below. |
| `core.Party` | `apps/core/models/Party.py:5` | the supplier identity a document belongs to. Vendors are a `PartyRole` — never re-declare one. |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | "this policy applies to this department" scoping (same use as `hrm.HRPolicy.applicable_org_unit`). |
| `core.AuditLog` + `core.utils.write_audit_log` | `apps/core/models/AuditLog.py:5`, `apps/core/utils.py:6` | audit rows for publish / approve-revision / check-out verbs (6.8 precedent: `run_renewal_alerts_audited`). |
| `core.utils.next_number` | `apps/core/utils.py` | the `PDOC-#####` / `PPOL-#####` / `PKR-#####` prefixes via `TenantNumbered`. |
| `scm.SupplierContract` [SC-] | `apps/scm/models/SupplierRelationshipManagement/SupplierContracts.py:13` | the agreement a warranty/SOW/insurance certificate hangs off. **6.8 extended this rather than declaring a second contract — 6.19 does the same.** |
| `scm.SupplierProfile` | `apps/scm/models/SupplierRelationshipManagement/SupplierProfiles.py:12` | supplier qualification context (tier) shown on a supplier's document shelf. |
| `scm.PurchaseOrder` [PO-] | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:15` | the order a spec/drawing/warranty attaches to. Owned by SCM 4.1 (L36) — FK by string. |
| `scm.PurchaseRequisition` [PR-] / `scm.RFQ` / `scm.GoodsReceiptNote` | `.../PurchaseRequisitions.py:14`, `Rfqs.py:12`, `GoodsReceiptNotes.py:15` | exist; **deliberately not FK'd this pass** (see *Deferred*). |
| `procurement.SourcingEvent` [—] | `apps/procurement/models/SourcingTendering/SourcingEvents.py:21` | the tender a quote/bid pack belongs to. |
| `procurement.RfxEvent` | `apps/procurement/models/RfxManagement/Events.py:20` | RFP/RFI events — the consumer of the RFP templates in the knowledge library. |
| `procurement.ContractClause` | `apps/procurement/models/ContractsManagement/Clauses.py:18` | **the clause library already exists** (title/category/body/version/`is_pre_approved`/`is_active`). 6.19 must NOT build a second one. |
| `procurement.RequisitionTemplate` [RQT-] | `apps/procurement/models/RequisitionManagement/Templates.py:16` | **the requisition template library already exists** (6.2). 6.19's knowledge library is about *how-to* content, not executable requisition blueprints. |
| `procurement.ProcurementAlert` | `apps/procurement/models/DashboardPortal/ProcurementAlerts.py:26` | **the reuse target for every expiry/review reminder.** `KIND_CHOICES` already carries `deadline`/`contract`; `link_url` + `due_at` + `severity` + open→acknowledged→resolved is exactly the inbox a document-expiry scan should raise into. |
| `procurement.ContractsManagement.run_renewal_alerts` | `apps/procurement/models/ContractsManagement/Renewals.py:55` | **the pattern to copy** for a "Run document reminders" verb: idempotent against open duplicates, row-locked dedupe, returns `{"raised", "skipped_open"}`, wrapped by an `_audited` variant. |
| `accounting.Currency` | used live by `RequisitionTemplate.currency` | the currency on a policy spend limit. |
| `core.forms._common.ALLOWED_DOC_EXTENSIONS` / `MAX_UPLOAD_BYTES` | `apps/core/forms/_common.py:16, :22` | **the upload validation contract already exists** (14 extensions, 20 MB). `core.forms.DocumentForm.clean_file` (`apps/core/forms/Document.py:13`) is the exact validator to mirror. |
| `pdfplumber==0.11.10` | `requirements.txt:14` | **already a declared dependency**, imported LAZILY by `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:418 _pdf_text` with a documented graceful fallback. This is the whole basis of the full-text bullet. |

### Spine entities VERIFIED NOT to exist

1. **No `documents` app.** `Glob apps/*/apps.py` returns exactly `core, accounts, tenants, dashboard, crm, accounting, hrm, scm, inventory, procurement`. **Module 13 DMS is unbuilt** — so nothing can be deferred *to code that exists*; it can only be deferred to a future module. 6.19 must be self-sufficient.
2. **No `procurement.Contract`.** `ContractsManagement/` holds `ContractClause`, `ContractClauseLink`, `ContractSigner`, `ContractMilestone` [CMI-], `ContractAmendment` [CAM-] — all hanging off `scm.SupplierContract`.
3. **No `core.Item` / catalog master.** `procurement.CatalogItem` (`CatalogItems.py:17`) carries `category_text` as free text. A document "category" therefore cannot FK a commodity taxonomy — use a choices field + free tags.
4. **No tag / taxonomy table anywhere.** No `Tag`, no `Keyword`. Tagging must be a normalized `CharField`, not a new M2M (that would be model #5).
5. **No search infrastructure.** `config/settings.py:102` = `django.db.backends.mysql`; `config/settings_test.py:10` = `sqlite3`. **No Elasticsearch, no Celery, no `SearchVector`.** A MySQL `FULLTEXT` index would not exist under the SQLite test runner, so it cannot be relied on. Search is `icontains` over indexed columns — say it plainly in the UI.

### The ruling on `core.Document` (asked for explicitly)

**Answer: (c) both — but with a hard boundary, and 6.19 does not touch `core.Document`'s schema.**

`core.Document` stays exactly what it is: the **generic, one-off attachment** for any record, tenant-scoped, with
its own `core:document_*` CRUD, already FK'd by `SupplierInvoice.document`. Nothing in 6.19 migrates it, adds
fields to it, or deprecates it.

6.19 declares its **own procurement-scoped repository record** because `core.Document` cannot express any of the
five bullets without becoming a Module 0 schema change that ripples into every app:

* Its `version` is a **flat `CharField(20)` with no revision chain** — you cannot answer "what was v2, who approved
  it, what changed" (the Version Control bullet). Every product surveyed treats a revision as a *row*, not a string.
* It has **no owner, no status, no lifecycle** — so "only the latest **approved** version is accessible" is
  unexpressible.
* It has **no expiry / review date** — the warranty-and-certificate half of the Central Repository bullet
  (SAP Ariba SLP, Ivalua, Coupa SIM all model this) has nowhere to live.
* It has **no extracted text and no tags** — the Full-Text Search bullet needs both, and putting a `TextField` of
  PDF text on Module 0's generic attachment would load it into every app's document list.
* Its link is a **GenericForeignKey**, which cannot be joined or faceted, and cannot be tenant-filtered at the
  queryset level — a cross-tenant IDOR surface on a list page that must offer "filter by supplier / contract / PO".

**What 6.19 owns now vs. what waits for Module 13:** 6.19 owns the *procurement* shelf — procurement document
types, procurement metadata, a linear approved-revision chain, an advisory check-out lock, the policy library, the
template library, and keyword search. Module 13 owns the *enterprise* DMS — folder hierarchies and virtual folders
(13.4), branching/merge and redline diff (13.2), the visual approval-workflow designer (13.3), custom metadata
schemas and controlled vocabularies (13.5), faceted/semantic/NL search and saved-search alerts (13.6),
document-level permission matrices, watermarking, DRM and DLP (13.7), records/retention automation and legal hold
(13.9), archival/PDF-A/WORM (13.14), and wikis (13.17). When Module 13 lands, `ProcurementDocument` becomes a
*view onto* the DMS the same way `procurement.*` became a layer around `scm`'s spine — note the future migration in
the model docstring, exactly as `RequisitionTemplate` notes the `core.Item` migration.

### Sibling research files checked

`research-procurement-6.2 / 6.5 / 6.9 / 6.10 / 6.11 / 6.12 / 6.13 / 6.14` exist. None of them cataloged a document
repository; 6.13 settled attachments by reusing `core.Document` for the single captured invoice PDF, and 6.8
settled the clause library. Neither deferred anything explicitly to 6.19, so this is a fresh backlog.

---

## Leaders surveyed (with source links)

1. **SAP Ariba (Contracts / Strategic Sourcing)** — the reference implementation of a *workspace document library*:
   folders and nested subfolders, documents attached to review/approval tasks, folder-level access control, a
   single **Main Agreement** Word document plus multiple **Contract Addenda** and any-format supporting documents,
   documents stored on the *template* so they auto-appear in every project created from it, conditional documents,
   and delete blocked while a document is inherited from a template or bound to a task.
   [Using and Organizing Documents](https://learning.sap.com/courses/sap-ariba-contracts-workspace-template-administration/using-and-organizing-documents) ·
   [Publishing Templates and Version Control](https://learning.sap.com/courses/sap-ariba-contracts-workspace-template-administration/publishing-templates-and-version-control)
   (templates are versioned on republish; optional Word addenda are version-controlled too).
2. **SAP Ariba Guided Buying** — the **policy-content** reference. A rich-text **Policy section** is edited directly
   onto the buyer landing page, and a *smart policy engine* defines rules that flag a violation **at request time**
   rather than after submission, with rules that either allow or disallow the exception; persona-based landing
   pages surface the right forms and policies per user.
   [SAP guided buying](https://www.sap.com/products/spend-management/procure-to-pay/features/guided-buying.html) ·
   [Configuring landing pages & procurement policies](https://blogs.sap.com/2018/11/19/ariba-guided-buying-configuring-and-managing-landing-pages-procurement-policies/)
3. **SAP Ariba Supplier Lifecycle & Performance** — the **expiry** reference. Certificate-type questions carry real
   expiration dates; the record moves to **Expiring** then **Expired**; the primary supplier manager and the project
   owner get e-mail notifications for upcoming and past expirations, targeted either at one certificate or the whole
   questionnaire; suppliers supply, approvers approve/deny.
   [Characterizing Supplier Certificate Management](https://learning.sap.com/courses/managing-modular-questionnaires-and-supplier-certificates/characterizing-supplier-certificate-management)
4. **Coupa (Source-to-Contract / CLM + SIM)** — a single searchable repository with **metadata tagging** for
   executed and draft contracts, configurable templates and clause libraries, a "prevailing terms" roll-up across
   several agreements with one counterparty, and contracts linked to POs, supplier records and spend. Its data model
   is explicit about **contract types** (`Master`, `Amendment`, `Contract`, defaulting to `Contract`), and
   attachments are a first-class object attachable to most core and transactional resources; supplier-side
   attachment upload/management is a documented portal capability. SIM standardizes the request/approval/maintenance
   of supplier data including **insurance and quality certificates**.
   [Coupa CLM](https://www.coupa.com/products/source-to-contract/contract-management/) ·
   [Contract Import (contract types + zipped attachments)](https://compass.coupa.com/en-us/products/product-documentation/integration-technical-documentation/coupa-core-flat-files-(csv)/flat-file-(csv)-import/contract-import) ·
   [Upload and Manage Attachments](https://compass.coupa.com/en-us/products/product-documentation/supplier-resources/for-suppliers/coupa-supplier-portal/contract-collaboration/upload-and-manage-attachments)
5. **JAGGAER (Contracts / Contracts AI)** — centralized repository with **full-text search across contracts *and*
   attachments** regardless of original location or format, metadata filtering, AI-extracted key terms indexed for
   retrieval, obligation tracking with alerts to responsible parties, renewal reminders, and a clause/template
   library organized **by region, business unit and contract type** with version control during drafting/redline and
   staged approvals keyed to value, type and risk.
   [JAGGAER Contracts](https://www.jaggaer.com/solutions/contracts) ·
   [Contracts AI](https://www.jaggaer.com/solutions/contracts-ai)
6. **GEP SMART / GEP Quantum** — repository + collaborative authoring in one; contracts searchable **by clause,
   field, term, party or any attribute** through unified free-text **and** structured search; template and clause
   libraries with alerts and event reminders; bulk ingestion of legacy contracts with automatic metadata
   structuring. GEP's own clause-library guidance frames the library as pre-approved language that carries forward
   into negotiation automatically.
   [Intelligent contract repository](https://www.gep.com/software/gep-smart/procurement-software/contract-management/intelligent-contract-repository) ·
   [Building a clause library](https://www.gep.com/blog/technology/contract-standardization-clause-library)
7. **Ivalua** — "Contract 360": terms, **versions**, obligations, documents, stakeholders, risk, pricing and
   performance on one record; smart search combining full-text + metadata filtering; pre-approved template and
   clause libraries; **version control and audit trails**; automated alerts on expiration/renewal; role-specific
   dashboards; links out to sourcing events, supplier data, POs and invoices. Its supplier-management side is the
   clearest statement of the **document-validity problem**: detecting missing, expired or inconsistent documents
   (PDFs, certificates, compliance proofs) instead of chasing expiry dates by hand.
   [Ivalua CLM](https://www.ivalua.com/solutions/process/strategic-sourcing/contract-lifecycle-management-software/) ·
   [Ivalua supplier management](https://www.ivalua.com/solutions/process/strategic-sourcing/supplier-management/)
8. **Zycus iContract** — repository + authoring with **clause library, playbook-based fallback positions**, full
   version history where every edit stays auditable, and **side-by-side version comparison** during negotiation;
   geography- and industry-specific template and clause libraries.
   [Zycus iContract](https://www.zycus.com/solution/contract-management)
9. **Icertis (ICI)** — **smart tagging** with consistent metadata so contracts are filterable in seconds; full-text
   search across the actual language, not only metadata; **attributes** are typed and tagged into the document
   (Contract Effective Date, Entity Name, Vendor Name), with **Contract-Type-specific attributes** defined on the
   template; obligations are their own entities with fulfilment records and workflow.
   [What is a contract repository](https://www.icertis.com/learn/what-is-a-contract-repository/) ·
   [Contract visibility & search](https://www.icertis.com/contracting-basics/contract-visibility-search/) ·
   [ICI Obligation Management](https://ici-us-wiki01.icertis.com/ICIHelp8.2/index.php?title=ICI_Obligation_Management)
10. **Precoro** — the most *concretely documented* mid-market attachment model, and the closest fit to NavERP's
    scale: attachments on POs, warehouse requests, PRs, RFPs, receipts, invoices and expenses; **Internal vs
    External** sections on the PO (external is what the supplier receives); an explicit allow-list of formats
    (JPEG/PNG/TIFF/GIF/XML/CSV/PDF/MSG/ZIP/PPTX/FIG) with preview only for PDF/PNG/JPEG/GIF and named blocked
    formats; a **25 MB per-file cap**; optional **automatic propagation** PR→PO(Internal), RFP→PO(External),
    PO→Invoice/Receipt; and role-based rules — creators and approvers upload and delete, viewers download only.
    Admins can make attachments **mandatory** before a PR can be confirmed.
    [Working with attachments](https://help.precoro.com/working-with-attachments-in-precoro) ·
    [Attachments in purchase orders](https://help.precoro.com/attachments-in-purchase-orders)
11. **Procurify** — uploads **active and historical** contract documents into one repository to centralize renewal
    dates, payment terms and ownership, links contracts to POs to track spend against contract value, and pairs the
    repository with approval workflows and card limits so spend is on-policy *before* it happens.
    [Managing contracts in Procurify](https://success.procurify.com/en/articles/9001601-managing-contracts-in-procurify) ·
    [Platform features](https://www.procurify.com/platform/features/)
12. **Basware Vault** — the **retention/records** reference: documents archived for a legally required retention
    period (7 years default US, up to 15 years supported) and **automatically destroyed when it elapses**, centrally
    searchable and retrievable for tax audits, with digital signing/timestamping for integrity.
    [Compliant e-invoice archiving](https://www.basware.com/en/solutions/e-invoicing-network/e-invoicing-archive)
13. **Oracle Fusion Cloud Procurement / Procurement Contracts** — **attachment categories** classify contract
    supporting documents so reviewers can browse and review them by category on purchasing documents; contract
    expiration notification requires at least one named contact and a days-to-expiration that is shorter than the
    contract duration.
    [Using Procurement Contracts](https://docs.oracle.com/en/cloud/saas/sales/fasca/using-procurement-contracts.pdf) ·
    [R13 Procurement what's new (attachment categories)](https://www.oracle.com/webfolder/technetwork/tutorials/tutorial/cloud/r13/wn/r13-procurement-wn.htm)
14. **Policy-management category (ConvergePoint, Xoralia, Sprinto, RiskWatch)** — surveyed for the *policy library*
    bullet: a central library, authoring → multi-level approval → publish, **version-level attestation** where each
    acknowledgment record links to the specific policy *version* the reader saw (not just the title), per-policy
    **re-review cadence**, and attestation status reporting by team/department.
    [ConvergePoint attestation](https://www.convergepoint.com/policy-management-software/policy-management-document-attestation-and-acknowledgement) ·
    [Xoralia policy attestation](https://xoralia.com/policy-management-software/policy-management-software-attestation/) ·
    [Sprinto policy management](https://sprinto.com/products/policy-management/)

---

## Feature catalog (this sub-module only)

Priority key: **table-stakes** (nearly every leader has it) · **common** (most have it) · **differentiator** (a few
standouts).

### Bullet 1 — Central Document Repository

- **One tenant-wide register of procurement files** — every quote, spec, warranty, certificate and drawing in one
  searchable list instead of scattered per-transaction attachments · seen in: Coupa, JAGGAER, GEP, Ivalua, Icertis,
  Procurify · priority: **table-stakes** · spine: **new table `ProcurementDocument`** (`core.Document` cannot carry
  the metadata — see ruling) · buildable now.
- **Document type / category classification** — a typed vocabulary (quote, specification, warranty, certificate of
  insurance, SOW, drawing, correspondence…) that drives filters and the register's facets · seen in: Oracle
  (attachment categories), Coupa (contract types Master/Amendment/Contract), Icertis (contract-type attributes),
  Ariba (main agreement vs addenda vs supporting) · priority: **table-stakes** · spine: `DOC_TYPE_CHOICES` on
  `ProcurementDocument` · buildable now.
- **Attach the document to the procurement object it belongs to** — supplier, agreement, tender, order · seen in:
  Coupa (contracts↔POs↔suppliers↔spend), Ivalua (POs/invoices/sourcing), Precoro (PR/PO/RFP/receipt/invoice),
  Procurify (contract↔PO) · priority: **table-stakes** · spine: **four nullable FKs** — `core.Party`,
  `scm.SupplierContract`, `scm.PurchaseOrder`, `procurement.SourcingEvent`. **Explicitly reject a
  GenericForeignKey**: the register must filter and facet on these columns, and a GFK is neither joinable nor
  tenant-filterable at the queryset level (an IDOR surface on a list page) · buildable now.
- **Confidentiality classification on the file** — public / internal / confidential / restricted, shown as a badge
  and filterable · seen in: Ariba (folder-level access), Ivalua (role-specific views), Icertis · priority: **common**
  · spine: mirror `core.Document.CLASSIFICATION_CHOICES` **verbatim for the first three values** so a future Module
  13 merge is a straight map · buildable now.
- **Upload allow-list + size cap** — named extensions, per-file ceiling, honest rejection message · seen in:
  Precoro (explicit allow-list, blocked list, 25 MB) · priority: **table-stakes** · spine: **reuse
  `ALLOWED_DOC_EXTENSIONS` + `MAX_UPLOAD_BYTES` and copy `core.forms.DocumentForm.clean_file`** — do not invent a
  second policy · buildable now.
- **Named owner / custodian per document** — who is answerable for keeping it current · seen in: Procurify
  (contract ownership), Ariba SLP (primary supplier manager), Ivalua · priority: **common** · spine:
  `owner` → `settings.AUTH_USER_MODEL` · buildable now.
- **Expiry, effective and next-review dates with a reminder scan** — warranties, insurance certificates and
  qualifications go stale; the system must surface *Expiring* and *Expired* rather than wait to be asked · seen in:
  Ariba SLP (Expiring/Expired + notifications to manager and owner), Ivalua (detect missing/expired documents,
  alerts), Oracle (expiration notification with days-to-expiration + contact), JAGGAER/GEP (event reminders) ·
  priority: **table-stakes** · spine: date fields on `ProcurementDocument` + **raise into the existing
  `procurement.ProcurementAlert`** (`kind="deadline"`), copying `run_renewal_alerts`'s idempotent, row-locked,
  `{"raised","skipped_open"}` shape · buildable now (**e-mail delivery is integration/later** — the alert inbox is
  the channel).
- **Retention / disposal date** — hold for the legally required period, then be able to see what is past retention
  · seen in: Basware Vault (7–15 years, auto-destroy on elapse) · priority: **common** · spine: `retention_until`
  date + an "over-retention" filter on the register. **Automatic destruction is out of scope** (needs a scheduler;
  Module 13.9/13.14 own it) · buildable now as a *flag*, not an action.
- **Supplier-visible vs internal-only** — what a vendor may see of the pack · seen in: Precoro (Internal/External
  PO attachment sections), Coupa (supplier-portal attachment upload) · priority: **common** · spine: a boolean on
  `ProcurementDocument` that 6.4's `VendorPortalAccess` can later gate on · buildable now as a *field*; the portal
  page itself belongs to 6.4.
- **Bulk / legacy import of an existing document pile** · seen in: GEP (bulk legacy contract ingestion), Coupa
  (zipped CSV + attachments) · priority: **differentiator** · **deferred** — a whole second UX; 6.9's
  `CatalogUploadBatch` is the pattern when it comes.

### Bullet 2 — Version Control

- **Revision rows, not a version string** — each upload creates an immutable revision with its own number, file,
  uploader, timestamp and change note · seen in: Ariba (version-controlled main agreement + addenda), JAGGAER,
  Ivalua ("versions" on Contract 360), Zycus (full version history, every edit auditable), Icertis · priority:
  **table-stakes** · spine: **new table `ProcurementDocumentRevision`**, modelled on the proven
  `crm.DocumentVersion` (`apps/crm/models/DocumentContract/DocumentVersions.py:6` — immutable, list+detail only,
  `unique_together (tenant, parent, version_no)`) · buildable now.
- **"Only the latest **approved** revision is accessible"** — the literal NavERP bullet. A revision is uploaded as
  *pending*, approved by a named user, and only then becomes the document's current revision; the register and every
  linked object resolve to that one · seen in: Ariba (published vs draft templates), JAGGAER (staged approvals by
  value/type/risk), Ivalua (workflow-driven approvals), Ariba SLP (approvers approve/deny certificate updates) ·
  priority: **table-stakes** · spine: `is_approved`/`approved_by`/`approved_at` on the revision +
  `current_revision_no` on the parent. **Use an integer pointer, not a circular FK** — the `crm.ContractDocument.
  current_version = PositiveSmallIntegerField` precedent (`Contracts.py:24`) · buildable now.
- **Check-out / check-in lock** — one editor at a time, with who holds it and since when, and an admin force-release
  · seen in: Ariba document actions, and it is Module 13.2's named bullet · priority: **common** · spine:
  `checked_out_by` + `checked_out_at` on `ProcurementDocument`, enforced in the upload-revision view. Keep it
  **advisory and simple** — a lock, a holder, a release verb. **Reservation alerts and forced-check-in policy are
  13.2** · buildable now.
- **Supersede / archive lifecycle** — draft → active → superseded → archived, so obsolete packs stop showing in the
  default register but stay for audit · seen in: Ariba (inactive-template folder convention), every CLM surveyed ·
  priority: **table-stakes** · spine: `STATUS_CHOICES` on `ProcurementDocument` · buildable now.
- **File integrity checksum on each revision** — proves the stored bytes are the bytes that were approved · seen in:
  Basware (digital signing + timestamping), Module 13.14 fixity · priority: **differentiator** · spine: a
  `sha256` hex CharField computed in-process at upload (`hashlib`, no dependency) · buildable now, cheap, and it is
  the honest version of "tamper-evident" without claiming WORM.
- **Side-by-side version diff / redline** · seen in: Zycus, Ivalua, JAGGAER · priority: **common** ·
  **OUT OF SCOPE** — 13.2 "Version Comparison & Diff View". Rendering a redline of two binary files is not a
  Django-template problem.
- **Branching / parallel versions & merge-back** · seen in: Module 13.2 · **OUT OF SCOPE.** Keep the chain linear.

### Bullet 3 — Procurement Policy Library

- **A browsable library of purchasing policies** — each with a category, a summary, the body, an owner and an
  effective date · seen in: Ariba guided buying (rich-text policy on the landing page), the policy-management
  category (ConvergePoint/Xoralia/Sprinto), Procurify (spend controls framed as policy) · priority: **table-stakes**
  · spine: **new table `ProcurementPolicy`**, modelled on the proven `hrm.HRPolicy`
  (`apps/hrm/models/ComplianceLegal/Hrpolicy.py:5` — category/version/`previous_version` self-FK/org-unit
  scoping/status/effective_from) · buildable now.
- **The "limits" half of the bullet — spend thresholds stated as data** — "purchases over X need three quotes",
  "sole-source above Y needs VP sign-off" · seen in: Ariba smart-policy engine (rules evaluated at request time),
  JAGGAER (approvals keyed to value/type/risk), Procurify (limits built into cards) · priority: **common** · spine:
  `threshold_amount` + `accounting.Currency` + a `threshold_basis` choices field on `ProcurementPolicy`.
  **Advisory only** — 6.3's `ApprovalRoutingRule` (`resolve_routing`) is the enforcing engine and already exists;
  the policy record documents the rule for humans and must say so in its docstring and on the page. Live
  enforcement at requisition time is 6.3's, not 6.19's · buildable now.
- **Policy versioning with a supersession chain** — v1.0 → v1.1 → v2.0, previous versions readable · seen in: the
  policy-management category (version-level attestation), Ivalua/Ariba template republish · priority:
  **table-stakes** · spine: `version_number` + `previous_version` self-FK (HRM precedent) · buildable now.
- **Draft → published → archived, with a publish verb** — an unpublished policy is not "the rules" · seen in:
  Ariba (publish templates), policy-management category (authoring → approval → distribute) · priority:
  **table-stakes** · spine: `status` + a POST-only `publish` verb writing `published_at` and a `core.AuditLog` row ·
  buildable now.
- **Departmental scoping** — a policy that applies to one org unit only · seen in: JAGGAER (clause sets by region /
  business unit), Ariba (persona landing pages), Ivalua · priority: **common** · spine: `applies_to` →
  `core.OrgUnit`, blank = whole tenant (HRM precedent) · buildable now.
- **Next-review date + stale-policy surfacing** — policies rot; the library must show which are overdue for review ·
  seen in: policy-management category (re-review cadence), Module 13.17 "stale content alerts" · priority: **common**
  · spine: `next_review_on` + a register filter + the same `ProcurementAlert` scan as document expiry · buildable now.
- **The policy's PDF lives in the repository, not in a second FileField** · priority: **common** (design call, not a
  product feature) · spine: `ProcurementPolicy.document` → `ProcurementDocument` (nullable). This is what makes 6.19
  one sub-module instead of two unrelated halves, and it means policy PDFs are covered by revision control and
  full-text search for free · buildable now.
- **User acknowledgement / attestation tracking** — who signed off which *version* · seen in: the whole
  policy-management category, and it is the strongest single feature there · priority: **table-stakes in that
  category** · **PARKED → 6.17** (NavERP.md 6.17 bullet: *"Policy Management & Acknowledgment — Repository for
  procurement policies and tracking of user sign-offs"*). 6.19 owns the **library**; 6.17 owns the **sign-off
  ledger**. Leave `requires_acknowledgment` as a boolean on `ProcurementPolicy` so 6.17 has a hook to FK — the
  `hrm.PolicyAcknowledgment` shape (`policy` FK + `employee` FK + `status` + `acknowledged_at`,
  `unique_together (tenant, policy, employee)`) is the model 6.17 should copy.

### Bullet 4 — Best Practices & Templates

- **A library of reusable sourcing/negotiation resources** — RFP and RFQ templates, bid-evaluation scorecards,
  negotiation playbooks, checklists and how-to guides, each with a type, an audience and a status · seen in: Ariba
  (sourcing content library of reusable line items, lots, sections, questions and attachments; templates stored so
  they auto-appear in new projects), JAGGAER (industry-specific templates, 80%-reusable clause sets), GEP (template
  + clause libraries), Zycus (playbook-based fallback positions, geography/industry template libraries), Ivalua
  (pre-approved template and clause libraries) · priority: **table-stakes** · spine: **new table
  `KnowledgeResource`** · buildable now.
- **Playbook / fallback-position content** — "here is the position to open with, here is the fallback, here is the
  walk-away" · seen in: Zycus (playbooks), GEP (approved language carried forward), JAGGAER · priority:
  **differentiator** · spine: `body` TextField on `KnowledgeResource` + a `resource_type="negotiation_playbook"`
  value · buildable now (as authored content — automatic carry-forward into a draft is 13.16).
- **Usage tracking on a template** — which resources are actually used, and when they were last used · seen in:
  Ivalua (CLM analytics tracks clause utilization), GEP (repository intelligence) · priority: **differentiator** ·
  spine: `usage_count` + `last_used_at` on `KnowledgeResource`, incremented by a POST-only **"Use this resource"**
  verb that also writes a `core.AuditLog` row. This is the one place a counter is honest — it is a click, not a
  derived metric · buildable now.
- **The downloadable artifact is a repository document** — the .docx RFP template is a `ProcurementDocument`, so it
  gets revisions and approval like everything else · priority: **common** · spine:
  `KnowledgeResource.document` → `ProcurementDocument` (nullable) · buildable now.
- **Applicability targeting** — this resource is for this category / this audience · seen in: JAGGAER (region/BU/
  contract type), Ariba (persona landing pages) · priority: **common** · spine: `category` choices +
  `audience` choices + free `tags` · buildable now.
- **Featured / pinned resources on a landing page** — the "start here" shelf · seen in: Ariba guided buying tiles,
  GEP procurement portal · priority: **common** · spine: `is_featured` boolean surfaced on the 6.19 library page ·
  buildable now.
- **Executable templates that generate a transaction** · seen in: Ariba (project templates create the workspace) ·
  **ALREADY BUILT / out of scope** — `procurement.RequisitionTemplate` (6.2) already applies into a
  `scm.PurchaseRequisition`, and 6.6 `RfxEvent` + `RfxQuestion` already build questionnaires. 6.19's library is
  **guidance content**, not a second executable template engine. Cross-link, do not duplicate.
- **Clause library** · seen in: every CLM surveyed · **ALREADY BUILT** — `procurement.ContractClause` (6.8).
  `KnowledgeResource` must not become a second one.

### Bullet 5 — Full-Text Search & Indexing

- **Search inside the text of uploaded PDFs, not just their titles** — the bullet, literally · seen in: JAGGAER
  (full-text across contracts *and* attachments), GEP (unified free-text + structured search), Ivalua (smart search
  full-text + metadata), Icertis (search the actual language, not only metadata) · priority: **table-stakes in the
  market** · spine: **an `extracted_text` TextField on `ProcurementDocument`**, populated best-effort at
  revision-upload time by a **lazy, optional `pdfplumber` import with a graceful no-op fallback** — the exact
  contract already proven by `apps/procurement/views/InvoiceVoucherManagement/SupplierInvoices.py:418 _pdf_text`
  (returns `("", [honest warning])` when the library is absent, when the file cannot be read back, when the PDF is
  malformed, or when it has no text layer). Plain-text uploads (`.txt`, `.csv`) can be decoded directly. **The page
  must never say "OCR"** — the 6.13 contract already forbids that wording and a scanned PDF genuinely yields
  nothing · buildable now.
- **Combined keyword search over title + description + tags + extracted text** · priority: **table-stakes** ·
  spine: a single `Q(title__icontains) | Q(description__icontains) | Q(tags__icontains) |
  Q(extracted_text__icontains)` on `ProcurementDocument`. **`icontains`, not FULLTEXT**: production is MySQL
  (`settings.py:102`) but tests run on SQLite (`settings_test.py:10`), so a `FULLTEXT` index would not exist under
  test. Say this plainly in the model docstring and cap `extracted_text` length at ingest (e.g. first ~200k chars)
  so one pathological PDF cannot bloat the row · buildable now.
- **Metadata / structured filtering alongside the keyword box** — type, status, classification, owner, supplier,
  expiry window · seen in: Coupa (metadata tagging), JAGGAER (metadata filtering), Icertis (smart tagging),
  Ivalua · priority: **table-stakes** · spine: indexed columns on `ProcurementDocument` + the standard NavERP
  filter contract (every dropdown's choices passed into the view context) · buildable now.
- **Free tagging** · seen in: Coupa, Icertis (smart tagging) · priority: **common** · spine: a normalized
  comma-separated `tags` CharField with a `tag_list` property. **Not** a `Tag` table — that is a fifth model for
  little gain at this scale · buildable now.
- **A visible "re-index" verb** — re-run extraction over documents whose text is empty, after the library is
  installed or a bad upload · priority: **differentiator** · spine: a POST-only bulk action on the register that
  returns `{"indexed", "skipped"}` and writes an audit row · buildable now.
- **AI/semantic search, clause detection, auto-tagging, NL query, OCR of scans** · seen in: JAGGAER Contracts AI,
  GEP Quantum extraction agents, Icertis AI extraction, Ivalua clause classification · priority: **differentiator**
  · **OUT OF SCOPE** — needs OCR/ML infrastructure and is NavERP 13.5/13.6.
- **Saved searches with new-match alerts** · seen in: Module 13.6 · **OUT OF SCOPE** (needs a scheduler).

### Beyond the bullets (found in the market, worth recording)

- **Prevailing-terms roll-up across several documents for one counterparty** (Coupa) — a supplier's document shelf
  showing the current warranty, the current insurance certificate, the current NDA. · priority: **differentiator** ·
  spine: **no new table** — a computed panel on the supplier-filtered register (`supplier` FK + `status="active"` +
  latest by type). Cheap and high-value; include it if the pass has room, as a filtered register view.
- **Mandatory-attachment rules** ("a PR over £10k cannot be confirmed without a quote") (Precoro) · priority:
  **common** · **PARKED** — it is an enforcement rule on the requisition flow, which is 6.2/6.3's surface, and it
  needs `scm.PurchaseRequisition` write hooks. Record it as a `ProcurementPolicy` entry instead.
- **Obligation extraction and fulfilment tracking** (Icertis, JAGGAER, Ivalua) · **ALREADY BUILT / parked** —
  `procurement.ContractMilestone` (6.8) is NavERP's obligation record.
- **Document-level permission matrices, watermarking, DRM, DLP** (Ivalua role views, Ariba folder ACLs) ·
  **OUT OF SCOPE** — 13.7. NavERP's tenant + `@login_required` scoping plus the `classification` badge is the
  honest level for this pass.

---

## Recommended build scope (this pass — 4 models)

All four are tenant-scoped (`TenantOwned` / `TenantNumbered` from `apps/procurement/models/_base.py`), all get full
CRUD (list with working filters + create + detail + edit + POST-only delete), and all live under
`apps/procurement/{models,forms,views,urls}/DocumentKnowledgeManagement/` with templates under
`templates/procurement/documents/<entity>/{list,detail,form}.html`.

1. **`ProcurementDocument`** [**PDOC-**] — *the procurement repository card: one row per controlled document, with
   its metadata, its lifecycle, its expiry clock and its searchable text.*
   Covers bullets **1 (Central Document Repository)**, **2 (Version Control — the parent half)**, **5 (Full-Text
   Search)**.
   Fields justified by the catalog: `title`, `doc_type` (quote / specification / warranty / certificate /
   insurance / sow / drawing / correspondence / policy / template / other — Oracle attachment categories + Coupa
   contract types + Ariba main-vs-addenda), `description`, `tags`, `classification`
   (public/internal/confidential/restricted — first three verbatim from `core.Document`), `status`
   (draft/active/superseded/archived), `owner` → `AUTH_USER_MODEL`, `supplier_visible` (Precoro Internal/External),
   `effective_date`, `expires_on`, `review_on`, `retention_until` (Basware), `current_revision_no`
   (`PositiveSmallIntegerField`, **not** a circular FK — `crm.ContractDocument.current_version` precedent),
   `checked_out_by` / `checked_out_at` (Ariba check-out), `extracted_text` (pdfplumber, lazy + optional).
   **FKs (all verified, all nullable):** `core.Party` (supplier), `scm.SupplierContract`, `scm.PurchaseOrder`,
   `procurement.SourcingEvent`.
   Verbs: upload-revision, approve-revision, check-out / release, archive, re-index, run-expiry-reminders (raises
   `ProcurementAlert`).

2. **`ProcurementDocumentRevision`** — *one immutable revision of a repository document; the file itself lives
   here.*
   Covers bullet **2 (Version Control)**.
   Fields: `document` FK (CASCADE, `related_name="revisions"`), `revision_no`, `file` (FileField validated against
   `ALLOWED_DOC_EXTENSIONS` + `MAX_UPLOAD_BYTES`), `original_filename`, `file_size`, `sha256` (integrity, computed
   in-process), `change_note`, `is_approved` / `approved_by` / `approved_at` (the "only the latest **approved**
   version is accessible" half of the bullet), `uploaded_by`, `uploaded_at`.
   `unique_together (tenant, document, revision_no)`, `ordering = ["-revision_no"]`, list + detail only — never
   edited (the `crm.DocumentVersion` posture, `DocumentVersions.py:6`).
   **FKs:** `procurement.ProcurementDocument`, `AUTH_USER_MODEL`.

3. **`ProcurementPolicy`** [**PPOL-**] — *one versioned purchasing rule/limit/guide in the tenant's policy library.*
   Covers bullet **3 (Procurement Policy Library)**.
   Fields: `title`, `policy_type` (purchasing_rule / approval_limit / competitive_bidding / sole_source /
   supplier_code_of_conduct / ethics_conflict / sustainability / data_security / other), `summary`, `body`,
   `version_number`, `previous_version` self-FK (SET_NULL — supersession chain, HRM precedent), `status`
   (draft/published/archived), `effective_from`, `published_at`, `next_review_on`, `threshold_amount` +
   `threshold_basis` (the "limits" half — **advisory, 6.3 enforces**), `requires_acknowledgment` (a hook for 6.17,
   with no ledger built here), `owner`.
   **FKs:** `core.OrgUnit` (`applies_to`, blank = whole tenant), `accounting.Currency` (threshold currency — read
   only, no ledger effect, L29), `procurement.ProcurementDocument` (the policy PDF, so it inherits revisions and
   search), `AUTH_USER_MODEL`.
   Verb: publish (POST-only, writes `published_at` + `core.AuditLog`).

4. **`KnowledgeResource`** [**PKR-**] — *one shared best-practice resource: an RFP template, a bid-evaluation
   scorecard, a negotiation playbook, a checklist or a how-to guide.*
   Covers bullet **4 (Best Practices & Templates)**, and contributes to **5** (its `body` is searchable).
   Fields: `title`, `resource_type` (rfp_template / rfq_template / evaluation_scorecard / negotiation_playbook /
   checklist / guide / sample_document / training), `category` (commodity-ish free choices — there is no taxonomy
   table to FK), `audience` (requester / buyer / approver / legal / all), `summary`, `body` (the guidance itself,
   rendered on the detail page), `tags`, `status` (draft/published/archived), `is_featured`, `usage_count` +
   `last_used_at` (Ivalua clause-utilization / GEP repository-intelligence), `review_on`, `owner`.
   **FKs:** `procurement.ProcurementDocument` (the downloadable artifact), `AUTH_USER_MODEL`.
   Verb: "Use this resource" (POST-only, increments `usage_count`, stamps `last_used_at`, writes `core.AuditLog`).

**Auto-number prefixes to reserve:** `PDOC`, `PPOL`, `PKR`. (`ProcurementDocumentRevision` is a numbered *child* —
it takes `revision_no` within its parent, not a tenant-wide number, exactly like `crm.DocumentVersion`.)

**Sidebar entry to add:** one `LIVE_LINKS["6.19"]` block mapping the five NavERP bullets — Central Document
Repository → `procurement:pdoc_list`; Version Control → the revision register (or `procurement:pdoc_list?status=…`);
Procurement Policy Library → `procurement:ppolicy_list`; Best Practices & Templates → `procurement:pkr_list`;
Full-Text Search & Indexing → `procurement:pdoc_search` (or the register's `?q=` deep link, following the 6.14
precedent of deep-linking a bullet to a filtered register).

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Policy acknowledgement / user sign-off ledger + attestation reporting** → **6.17** (its own bullet: *Policy
  Management & Acknowledgment*). 6.19 leaves `requires_acknowledgment` as the hook; 6.17 copies
  `hrm.PolicyAcknowledgment`'s shape and FKs `procurement.ProcurementPolicy`.
- **Tamper-proof audit log of every document view/download** → **6.17** (*Audit Trail & Logging*). 6.19 writes
  `core.AuditLog` rows for its own verbs, but the immutable-log product is 6.17's.
- **Supplier document requirements as a qualification gate** ("a strategic supplier must hold a current
  ISO 9001") → **6.16 Supplier Performance & Evaluation** / SCM 4.2 `SupplierProfile` qualification. 6.19 stores
  and expires the certificate; it does not decide whether the supplier is qualified.
- **Mandatory-attachment enforcement on requisition submit** → **6.2 / 6.3** (the requisition + approval surface).
- **Vendor-facing document upload and download** → **6.4** (`VendorPortalAccess` already gates the portal). 6.19
  ships the `supplier_visible` flag; 6.4 ships the page.
- **Clause library** → **6.8** (`ContractClause`, built). **Executable requisition templates** → **6.2**
  (`RequisitionTemplate`, built). **RFx questionnaires** → **6.6** (`RfxEvent`/`RfxQuestion`, built).
  **Contract obligations/milestones** → **6.8** (`ContractMilestone`, built).

---

## Deferred (later passes / integrations / Module 13)

| Area | Why deferred |
|---|---|
| **OCR of scanned PDFs, AI auto-tagging, clause detection, semantic / NL search** | Needs OCR + ML infrastructure that does not exist and is not being added. NavERP 13.5 *Full-Text Indexing & OCR* and 13.6 *Natural Language Query & AI Search*. The UI must not use the word "OCR". |
| **Elasticsearch / MySQL FULLTEXT relevance ranking** | No search service; and a `FULLTEXT` index cannot exist under the SQLite test runner (`config/settings_test.py:10`). `icontains` over `extracted_text` is the honest ceiling. |
| **Folder hierarchy / virtual folders / metadata inheritance** | NavERP 13.4 + 13.5. `doc_type` + `tags` + the four object FKs give the same findability without a tree. |
| **Version diff / redline, branching, merge-back** | NavERP 13.2. The revision chain stays linear. |
| **Document-level permission matrices, watermarking, DRM, DLP, secure viewer** | NavERP 13.7. Tenant scoping + `@login_required` + a `classification` badge is this pass's honest level. |
| **Automatic retention destruction, legal hold, WORM/PDF-A archival** | NavERP 13.9 / 13.14 and needs a scheduler. 6.19 stores `retention_until` and can *show* over-retention rows; it deletes nothing on a timer. |
| **E-mail notification of expiring documents** | No mail worker (the 6.8 renewal scan has the same limitation). Reminders land in `ProcurementAlert`; the run is a user-pressed verb, not a cron job. |
| **Bulk / ZIP import and legacy migration** | A second UX and a security surface (zip-slip). 6.9's `CatalogUploadBatch` is the pattern when it is scheduled. |
| **A `Tag` table with autocomplete and a controlled vocabulary** | Fifth model; 13.5 *Controlled Vocabulary & Thesauri*. A normalized `tags` CharField serves the register filter now. |
| **File preview / thumbnails in the browser** | Precoro previews PDF/PNG/JPEG/GIF; NavERP can link to the file and let the browser decide. Inline rendering of user-uploaded files is a stored-XSS surface and needs `Content-Disposition`/CSP work — do it deliberately later. |
| **Requisition / RFQ / GRN document FKs** | Kept to four link FKs this pass so the register's filters stay comprehensible. `scm.PurchaseRequisition`, `scm.RFQ` and `scm.GoodsReceiptNote` all exist and are one migration away when a real need appears. |
| **Prevailing-terms panel per supplier** | Nice-to-have computed view (no table). Ship only if the pass has room after the four models have real CRUD. |
