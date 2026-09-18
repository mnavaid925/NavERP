# Review Wave Report — Projects 7.14 Client & External Collaboration

> Conducted strictly serially against commit range `c3ccc923bf123c6db9ce35de9717794f83a4d01e...HEAD`
> Date: 2026-09-18

---

## 1. Executive Summary

- **Scope Coverage**: 5 of 5 NavERP.md 7.14 bullets fully implemented with 6 models, 5 forms, 23 view endpoints, 16 templates, seeder, migration 0021, and LIVE_LINKS navigation.
- **Smoke Gate**: Passed 110/110 checks in `temp/smoke_714.py` (all URLs HTTP 200/302, POST-only verbs 405 on GET, cross-tenant IDOR returns 404).
- **L33 Badge Compliance**: 100% compliant (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`). Zero forbidden badge classes.
- **L29/L36 AR Ledger Compliance**: Accounting owns the invoice ledger; `ProjectClientInvoice` connects to `accounting.Invoice` without creating a duplicate AR ledger.

---

## 2. Reviewer Findings

### Reviewer 1: `code-reviewer`
- **Finding CR-1 (Important)**: Action verbs in `ClientFeedbacks.py` (`cfb_approve`, `cfb_reject`), `StatementOfWorks.py` (`sow_activate`, `sow_amendment_create`), and `VendorHandoffs.py` (`vhd_accept`, `vhd_reject`) update database records and emit `write_audit_log` without explicit `with transaction.atomic():` blocks. Wrapping each mutation in an atomic transaction guarantees atomicity between status updates and audit trail entries.

### Reviewer 2: `explorer`
- **Result: PASS**. All five capability areas verified:
  1. Client Portal & Visibility (`ClientPortalAccess` [`CPA-`])
  2. Client Feedback & Approvals (`ClientApprovalRequest` [`CFB-`])
  3. Contract & SOW Management (`StatementOfWork` [`SOW-`] + `SOWAmendment` [`SWA-`])
  4. External Vendor Coordination (`VendorHandoff` [`VHD-`])
  5. Billing & Invoicing to Clients (`ProjectClientInvoice` [`PCI-`])

### Reviewer 3: `frontend-reviewer`
- **Result: PASS**.
  - All 16 templates extend `base.html`, include Lucide icons, breadcrumbs, card containers, form validation states, and empty states.
  - All badges are color-named strictly from `theme.css`.

### Reviewer 4: `performance-reviewer`
- **Finding PR-1 (Important)**: In `StatementOfWorks.py`, `StatementOfWork.total_amendments` and `StatementOfWork.effective_value` call `.filter(status="approved")` on the `amendments` relation. Because `.filter()` invalidates Django's prefetch cache, calling these properties in `sow_list` triggers N+1 queries despite `prefetch_related("amendments")`. Iterating `self.amendments.all()` using Python list comprehension preserves the in-memory prefetch cache and eliminates N queries.
- **Finding PR-2 (Important)**: In `ClientInvoices.py`, `pci_list` template evaluates `obj.project.client.name`, but the queryset only specifies `select_related("project")`. Adding `"project__client"` to `select_related` prevents an extra query per invoice line item on the list page.

### Reviewer 5: `qa-smoke-tester`
- **Result: PASS**.
  - Verified with `temp/smoke_714.py`: 110 automated assertions passing.
  - Confirmed 200 OK on list/detail/create/edit views, 405 on GET to POST-only verbs, and verified that `pci_generate_invoice` writes draft customer invoice to accounting AR ledger.

### Reviewer 6: `security-reviewer`
- **Result: PASS**.
  - All views enforce `@login_required` and scope model queries by `tenant=request.tenant`.
  - All forms enforce `_reject_foreign` cross-tenant foreign key protection.
  - Cross-tenant IDOR protection verified for all models in both directions (404 Not Found).

---

## 3. Deduplicated Action Items for Phase 5 (Code-Fixer)

1. **[Important] (CR-1)**: Wrap state transition verbs in `ClientFeedbacks.py`, `StatementOfWorks.py`, and `VendorHandoffs.py` in `with transaction.atomic():`.
2. **[Important] (PR-1)**: Update `StatementOfWork.total_amendments` and `effective_value` to iterate `self.amendments.all()` in Python to avoid busting `prefetch_related` cache.
3. **[Important] (PR-2)**: Add `"project__client"` to `select_related` in `pci_list` (`ClientInvoices.py`).
