# Gaps Register: eCommerce Sub-module 9.17 (B2B & Wholesale Commerce)

> **Context**: Sub-module 9.17 delivers Corporate Buyer Accounts (`B2bCompanyAccount`), Tiered Role Hierarchies with approval limits (`B2bCompanyUser`), Quote Request & Negotiation workflows (`B2bQuoteRequest`, `B2bQuoteItem`), Requisition Kits & Quick Order Matrix (`B2bQuickOrderTemplate`, `B2bQuickOrderItem`), Bulk Matrix Ordering with CSV spreadsheet import, PunchOut e-procurement simulation (cXML/OCI), and a centralized B2B Wholesale Hub console (`b2b_wholesale_hub`).
> All core CRUD operations, multi-tenancy isolation (`tenant=request.tenant`), credit exposure tracking, state machine transitions, order conversion, review findings burndown (100% resolved), dedicated test suite (48 tests passing, 0 failures), and module documentation are complete.

---

### GAP-9.17-01: Production cXML / OCI HTTPS Gateway to SAP Ariba & Coupa
- **Owner**: `ecommerce` / Sub-module 9.19 Integration & API Ecosystem
- **Waiting For / Blocked On**: Production buyer procurement system endpoint credentials (cXML POSR shared secret, buyer network domain/identity) and outbound HTTPS webhook dispatch worker.
- **Status**: `- [~]` Deferred (Simulated POSR initialization, cXML XML payload inspector, and PunchOut order return flow are fully functional in runtime simulator).
- **Done When**: Outbound cXML `PunchOutSetupRequest` and inbound `PunchOutOrderMessage` HTTP POST endpoints authenticate with SHA-256 against SAP Ariba, Coupa, and Jaggaer production gateways.

### GAP-9.17-02: Automatic General Ledger AR Invoice Posting on Quote Order Conversion
- **Owner**: `accounting` / Module 2 Financial Accounting & General Ledger
- **Waiting For / Blocked On**: Module 2 Accounts Receivable invoice generation hook (`accounting.Invoice`) triggered upon B2B quote order conversion under trade credit Net payment terms.
- **Status**: `- [~]` Deferred (Quote conversion automatically creates `EcommerceOrder`, updates B2B company account `credit_used`, and links converted order).
- **Done When**: Post-conversion hook dispatches an AR invoice and creates a balanced `JournalEntry` (debit Accounts Receivable, credit Sales Revenue) in Module 2.

### GAP-9.17-03: Multi-Level Sequential Buyer Approval Routing Workflows
- **Owner**: `ecommerce` / Sub-module 9.17 B2B & Wholesale Commerce
- **Waiting For / Blocked On**: Client enterprise organizational specification for multi-tier sequential approval hierarchies (e.g., Buyer -> Department Manager -> VP Finance).
- **Status**: `- [~]` Deferred (Role-based single-threshold checks are enforced: buyers cannot exceed `approval_threshold_amount` or `monthly_spend_limit`).
- **Done When**: Orders and quote requests exceeding approval thresholds enter a sequential approval queue requiring multiple stakeholder digital sign-offs before order release.
