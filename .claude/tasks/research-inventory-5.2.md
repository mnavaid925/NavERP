# Research — Inventory 5.2 Vendor / Supplier Management

> **RETROSPECTIVE ARTIFACT.** The 5.2 build landed (commits `a80a38eb..e220f522`, built 2026-08-22)
> without this phase-1 document being written first; it was authored after the fact to close the
> sequence gap and to record the domain survey and the ownership ruling that shaped the as-built
> scope. It documents decisions already committed — nothing here changed the build.

## Scope ruling (L36) — three of four bullets are SCM 4.2 pages

Module 5 ships after `scm` (4.1–4.2 already live), so the supplier **master** layer is owned by
Supplier Relationship Management and 5.2 re-points its sidebar bullets at those pages instead of
declaring a second supplier master:

| NavERP.md bullet | As-built target | Why |
|---|---|---|
| Supplier Directory | `scm:supplierprofile_list` (`scm.SupplierProfile`) | OneToOne on `core.Party`; tax_registration, primary contacts, tier/category, onboarding workflow, five due-diligence flags |
| Supplier Performance Tracking | `scm:scorecard_list` (`scm.SupplierScorecard`) | Delivery/quality/price/responsiveness scores derived from signals, derived overall + grade, manual override; risk overlay via `scm.SupplierRiskAssessment` |
| Contract & Terms Management | `scm:contract_list` (`scm.SupplierContract`) | Payment terms (`accounting.PaymentTerm` FK), validity window, value+currency, auto-renew + notice days, terms summary, linked `core.Document`; per-item lead times & MOQs live on `scm.SupplierCatalogItem` (`lead_time_days`, `min_order_qty`), not the contract header |

Re-declaring any of these in `inventory` would create two sources of truth for the same vendor.

## Product survey — what leading vendor/supplier-management products do per bullet

Surveyed SAP Ariba (Supplier Lifecycle & Performance), Coupa SXM, Jaggaer One, Ivalua,
Zycus iPerform, GEP SMART, Odoo Purchase, NetSuite SRM, Zoho-style interaction timelines, and
SAP S/4HANA MM business-partner + supplier evaluation.

1. **Directory** — every SRM treats this as master data around a business partner: tax IDs and
   remit-to details, contact roster, tiering (strategic/preferred/transactional), an onboarding or
   qualification status machine, and compliance/due-diligence flags. NavERP's spine already has all
   of it on `Party` + `PartyRole(role=supplier/vendor)` + `SupplierProfile`.
2. **Performance tracking** — scorecards computed over a period from delivery/quality/cost signals,
   letter grades, manual override, plus a separate risk assessment (financial/geopolitical/
   compliance/operational → risk index). Matches `SupplierScorecard` + `SupplierRiskAssessment`
   exactly; nothing for Module 5 to add.
3. **Contracts & terms** — header-level commercial terms (payment terms, validity, value, renewal)
   with item-level operational terms (lead time, MOQ, price) kept on catalog/price lines. Same split
   as `SupplierContract` / `SupplierCatalogItem`.
4. **Vendor communication log** — the weak spot across surveyed products: most bolt an activity
   stream onto the supplier record (Odoo chatter pattern) or scatter correspondence inside RFQ/PO
   threads. None offers a standalone, filterable buyer-vendor interaction log with follow-up
   tracking that survives independent of onboarding state. **This is 5.2's genuine gap.**

## The one new model — `inventory.VendorCommunication` [VC-]

As built (`apps/inventory/models/VendorSupplierManagement/VendorCommunications.py`):

- `party` FK → `core.Party`, **PROTECT**, pointed at the party rather than `SupplierProfile` so
  history survives for vendors whose SRM profile was never completed.
- `channel` ∈ email/call/meeting/site_visit/note · `direction` ∈ inbound/outbound (blankable) ·
  `subject` · `body` · `occurred_at` (default now) · optional `follow_up_on`.
- Follow-up semantics: today-or-later = *due*, strictly past = *overdue* — both the property and the
  list filter use `timezone.localdate()` so badge and filter cannot disagree at midnight.
- Per-tenant `VC-#####` numbering via the app's `TenantNumbered` base; `unique_together(tenant, number)`;
  indexes `(tenant, party) (tenant, channel) (tenant, follow_up_on) (tenant, occurred_at)` — the last
  backs the default `-occurred_at` list ordering on an unbounded log (migration `0004`).
- `clean()` rejects cross-tenant parties; provenance comes from `core.AuditLog` rows written by the
  shared CRUD helpers instead of a drift-prone `logged_by` column.
- Pages: `templates/inventory/vendor/vendorcommunication/{list,detail,form}.html`; detail carries the
  same-vendor "Other Interactions" panel (scoped + self-excluded server-side).

**Deliberately not built here:** vendor self-service portal (SCM 4.2 portal accounts), RFQ-side
correspondence (SCM 4.1), e-signatures (CRM 1.9), spend analytics (SCM 4.11).

Recommended scope: exactly **one model** — which is what shipped.
