# Research — Sub-module 7.14: Client & External Collaboration (Module 7 — `projects`)

Researched 2026-09-18 against the leading commercial Professional Services Automation (PSA), Project Portfolio Management (PPM), and Client Collaboration platforms: Kantata OX (formerly Mavenlink), Certinia PSA (formerly FinancialForce), Planview AdaptiveWork (Clarizen), Wrike for Professional Services, Scoro, and BigTime.

## The five NavERP.md bullets, mapped

1. **Client Portal & Visibility** — Branded external access, project progress views, and deliverable sharing.
   - Core Container: `ClientPortalAccess` [`CPA-`] (tenant, project FK, client contact `core.Party`, portal user optional FK, access token, permission flags: `can_view_progress`, `can_view_milestones`, `can_view_deliverables`, `can_view_financials`, `can_submit_feedback`, `is_active`, `expires_at`, `last_accessed_at`).
   - Visibility surface: `projects:cpa_list` staff-facing management console per Lesson L32 (staff manage external client permissions and invite tokens).

2. **Client Feedback & Approvals** — Review cycles, annotation tools, and formal sign-off workflows.
   - Core Entity: `ClientApprovalRequest` [`CFB-`] (tenant, project FK, deliverable name/document `core.Document` optional FK, milestone `ProjectMilestone` optional FK, requested_by user, assigned_contact `core.Party`, status: `draft`, `pending_review`, `approved`, `rejected`, `revision_requested`; review_notes, client_feedback, signed_by_name, signed_at, rejection_reason).
   - Approval Verbs: `cfb_approve` (records sign-off and timestamp), `cfb_reject` (captures client revision notes and returns deliverable to team).

3. **Contract & SOW Management** — Statement of work authoring, amendment tracking, and milestone billing linkage.
   - Core Entity: `StatementOfWork` [`SOW-`] (tenant, project FK, client `core.Party`, title, sow_number, billing_type: `fixed_fee`, `time_and_materials`, `milestone_based`, `retainer`; contract_value, currency `accounting.Currency` FK, start_date, end_date, status: `draft`, `under_review`, `active`, `amended`, `completed`, `terminated`; scope_summary, terms_and_conditions).
   - Amendment tracking: `SOWAmendment` [`SWA-`] (tenant, sow FK, amendment_number, effective_date, value_change, revised_scope, justification, status: `draft`, `approved`, `rejected`, approved_by, approved_at).
   - Verb: `sow_activate` (marks SOW active and baselines contract terms).

4. **External Vendor Coordination** — Third-party task assignment, deliverable handoffs, and vendor scorecards.
   - Core Entity: `VendorHandoff` [`VHD-`] (tenant, project FK, vendor `core.Party`, task `ProjectTask` optional FK, title, description, handoff_date, due_date, status: `assigned`, `in_progress`, `delivered`, `accepted`, `rejected`; deliverable_link, scorecard_rating: 1–5 scale, performance_notes, accepted_at, accepted_by).
   - Coordination Verbs: `vhd_accept` (accepts vendor deliverable and logs scorecard score), `vhd_reject` (rejects with deficiency notes).

5. **Billing & Invoicing to Clients** — Time-and-materials, fixed-fee, and milestone-based invoice generation.
   - Core Entity: `ProjectClientInvoice` [`PCI-`] (tenant, project FK, sow `StatementOfWork` optional FK, milestone `ProjectMilestone` optional FK, billing_type: `fixed_fee`, `time_and_materials`, `milestone`, `retainer`; billing_date, due_date, currency, amount, tax_amount, total_amount, status: `draft`, `ready_to_bill`, `invoiced`, `cancelled`; notes, `accounting.Invoice` optional FK per L29).
   - Verb: `pci_generate_invoice` (drafts an `accounting.Invoice` inside `transaction.atomic()` ensuring strict GL integration with no duplicate ledger).

---

## Recommended scope (5 domain models + 1 amendment child model)

- `ClientPortalAccess` [`CPA-`] — client external access & visibility permissions.
- `ClientApprovalRequest` [`CFB-`] — client review cycles and formal sign-offs.
- `StatementOfWork` [`SOW-`] — statement of work authoring and contract terms.
- `SOWAmendment` [`SWA-`] — SOW scope and value amendment tracking.
- `VendorHandoff` [`VHD-`] — external vendor coordination, deliverable handoffs, and scorecards.
- `ProjectClientInvoice` [`PCI-`] — client billing milestones, generation, and linkage to `accounting.Invoice`.

---

## Rulings

1. **Accounting owns the invoice ledger (L29 / L36).**
   `ProjectClientInvoice` is the project delivery billing schedule and draft milestone trigger. When billed, it links to or drafts canonical `accounting.Invoice` rows; it never stores a competing general ledger.
2. **Staff pages in sidebar (L32).**
   Staff sidebar navigation targets management registers (`cpa_list`, `cfb_list`, `sow_list`, `vhd_list`, `pci_list`), avoiding login-gated external client redirection.
3. **Core Party reuse (L28).**
   Clients and external vendors are `core.Party` records with roles `customer` and `vendor`/`subcontractor`.
4. **Verbs drive state machine transitions.**
   State changes (`cfb_approve`, `cfb_reject`, `sow_activate`, `vhd_accept`, `vhd_reject`, `pci_generate_invoice`) are POST-only views writing `core.AuditLog` rows (action string ≤ 10 chars).
5. **Theme.css color-named badges (L33).**
   Only `.badge-green`, `.badge-red`, `.badge-amber`, `.badge-info`, `.badge-muted`, `.badge-slate`.
