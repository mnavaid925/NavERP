# Review Findings: Sub-module 8.15 Contract & Subscription Management

**Base Commit**: `f64118d1453d8b4e05181cf64ba89d9a95ddb49f`
**Target App**: `apps/sales/` (Sub-module 8.15)
**Date**: 2026-10-22
**Status**: Deduplicated and Prioritized for Phase 5 (`code-fixer`)

---

## Executive Summary
Six serial review passes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) evaluated `f64118d1453d8b4e05181cf64ba89d9a95ddb49f...HEAD`. 

The architecture demonstrates flawless multi-tenancy (`TenantNumbered`, strict scoping on every query, 100% 404 on IDOR checks) and Core spine reuse (`core.Party`, `sales.CPQQuote`, `accounting.Currency`, `core.Document`). The reviewers identified 5 Critical issues (including a universal crash on audit logging across all 21 mutating views and invalid arguments on CPQ renewal quotes), 12 Important issues (transaction boundaries, chained N+1 lookups, missing status guards, filter dropdown completeness, and query consolidation), and 10 Minor issues.

---

## Findings Register

### Critical
- [x] **C1** — `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:210`: `customer_contract_generate_renewal_quote` view crashes with `TypeError: CPQQuote() got unexpected keyword arguments: 'title', 'grand_total'`. `CPQQuote` defines `name` (not `title`) and `total` (not `grand_total`). Fix: Pass `name=f"Renewal Quote for {contract.title}"`, `total=renewal_amount`, and remove `grand_total`. fixed — cdb70d21
- [x] **C2** — `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:84,138,167,188,222,254`, `CustomerSubscriptions.py:93,161,190,210,230,256,279`, `UsageMeterRecords.py:77,134,163,183,203`, `ContractObligations.py:92,156,185,208,233`: Universal crash across all 21 `write_audit_log` call sites. All call sites pass invalid keyword arguments `(tenant=..., user=..., action=..., model_name=..., object_id=..., object_repr=...)`. In `apps/core/utils.py`, the authoritative signature is `write_audit_log(user, obj, action, changes=None, tenant=None)`. Calling any mutating action causes `TypeError: write_audit_log() got an unexpected keyword argument 'model_name'` and 500s. Fix: Refactor all 21 call sites across all 4 view files to `write_audit_log(user=request.user, obj=instance, action=action, tenant=tenant)`. fixed — 6f183f41, 0a170743, 04657f67, 4ff436c6
- [x] **C3** — `apps/sales/forms/ContractSubscriptionManagement/UsageMeterRecords.py:44` & `ContractObligations.py:53`: Chained N+1 query vulnerability through `CustomerSubscription.__str__` (L18). In `UsageMeterRecordForm.__init__` and `ContractObligationForm.__init__`, `self.fields["subscription"].queryset` lacks `.select_related("account")`. Because `CustomerSubscription.__str__` accesses `self.account.name`, rendering `<select name="subscription">` triggers 1 + N queries against `core_party`. Fix: Add `.select_related("account")`. fixed — 08f2ac5a, a6a75cf3
- [x] **C4** — `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:236`: Un-guarded auto-renewal execution allows financial value inflation and duration distortion. View has zero status check, zero notice check, and fails to verify `contract.auto_renew is True`. Fix: Enforce `contract.status == "active"`, `contract.auto_renew is True`, notice period check, and wrap in `@transaction.atomic`. fixed — fe8de422
- [x] **C5** — `apps/sales/views/ContractSubscriptionManagement/UsageMeterRecords.py:177`: Un-guarded `usage_meter_record_calculate` resets `meter.status = "calculated"` even on already invoiced records (`status == "invoiced"`), compromising billing ledger integrity. Fix: Guard with `if meter.status == "invoiced": messages.error(request, "Cannot recalculate an already invoiced usage record.")`. fixed — 36e62c08

### Important
- [x] **I1** — `apps/sales/models/ContractSubscriptionManagement/ContractObligations.py:113`: `clean()` fails to enforce relational consistency between `subscription` and `contract`. Fix: Add `if self.subscription_id and self.subscription.contract_id and self.subscription.contract_id != self.contract_id: raise ValidationError({"subscription": "Associated subscription must belong to the selected contract."})`. fixed — 59cc3036
- [x] **I2** — `apps/sales/views/ContractSubscriptionManagement/ContractSubscriptionWorkspaces.py:52`: `urgent_contracts` checks `hasattr(contracts_qs, "order_date")` (which is never true for QuerySets) and conditionally duplicates query with non-existent method call. Fix: Simplify to direct `.order_by("end_date")[:5]`. fixed — 65277ac6
- [ ] **I3** — `apps/sales/views/ContractSubscriptionManagement/{CustomerContracts,CustomerSubscriptions,UsageMeterRecords,ContractObligations}.py`: Missing database transaction boundaries on state mutations and record creations. Fix: Decorate create, edit, delete, and action views with `@transaction.atomic`.
- [ ] **I4** — `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:181`: Missing status guard on `customer_contract_activate` allows activating terminated/expired contracts. Fix: Guard `if contract.status in ("active", "terminated", "expired"): messages.error(...)`.
- [ ] **I5** — `apps/sales/views/ContractSubscriptionManagement/CustomerSubscriptions.py:204,223`: Missing status guards on `customer_subscription_resume` (only paused subscriptions can be resumed) and `customer_subscription_pause` (only active or trialing subscriptions can be paused). Fix: Add status guards.
- [ ] **I6** — `apps/sales/views/ContractSubscriptionManagement/{CustomerContracts,CustomerSubscriptions,UsageMeterRecords}.py`: Destructive record deletions lack `@tenant_admin_required` and allow deleting active contracts or invoiced meter records. Fix: Add `@tenant_admin_required` and status validation.
- [ ] **I7** — `templates/sales/contractsubscriptionmanagement/{customersubscription,contractobligation,customercontract}/list.html`: Missing filter dropdowns in templates: `customersubscription/list.html:63` omits `account` select dropdown; `contractobligation/list.html:59` omits `assigned_to` select dropdown; `customercontract/list.html:63` omits `owner` select dropdown. Fix: Add `<select>` dropdowns to the respective filter bars.
- [ ] **I8** — `templates/sales/contractsubscriptionmanagement/customersubscription/list.html:54` & `apps/sales/views/ContractSubscriptionManagement/CustomerSubscriptions.py:63`: Stat card label reads "Total Annualized ARR" but renders monthly MRR. Fix: Compute and pass `total_arr` in view context and render `${{ total_arr|floatformat:2 }}`.
- [ ] **I9** — `apps/sales/views/ContractSubscriptionManagement/{ContractSubscriptionWorkspaces,RenewalAutomations}.py`: Fragmented sequential queries for metrics. Consolidate into unified conditional aggregates with `Count("id", filter=Q(...))` and eliminate dead query `urgent_subscriptions`.
- [ ] **I10** — `templates/sales/contractsubscriptionmanagement/{boards/renewal_automation_dashboard.html,customercontract/detail.html,customersubscription/detail.html}`: Template `.count` triggers redundant SQL queries on evaluated QuerySets. Fix: Replace `.count` with `|length` on evaluated lists.
- [ ] **I11** — `apps/sales/models/ContractSubscriptionManagement/{CustomerContracts,CustomerSubscriptions,ContractObligations}.py`: Missing compound indexes for high-frequency horizon scans. Add `(tenant, status, end_date)` to CustomerContract, `(tenant, contract)` to CustomerSubscription, and `(tenant, subscription)` to ContractObligation.
- [ ] **I12** — `apps/sales/forms/ContractSubscriptionManagement/CustomerSubscriptions.py:27`: `renewal_notice_days` has no default fallback if omitted from client post data, causing form validation failure on bare POST requests. Fix: Set initial default of 30 in form `__init__`.

### Minor
- [ ] **M1** — `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:13`: Unused import of `tenant_admin_required`. Fix: Apply to `customer_contract_delete`.
- [ ] **M2** — `apps/sales/forms/ContractSubscriptionManagement/CustomerContracts.py:65`: Narrow `account` queryset in form to customer roles: `Party.objects.filter(tenant=self.tenant, roles__role="customer").distinct()`.
- [ ] **M3** — `templates/sales/contractsubscriptionmanagement/contractobligation/list.html:28` & `boards/renewal_automation_dashboard.html:32`: Non-standard `stat-icon red`. Fix: Use `stat-icon orange`.
- [ ] **M4** — `templates/sales/contractsubscriptionmanagement/usagemeterrecord/detail.html:180`: None-safe display convention: add `|default:"—"` to `plan_code`.
- [ ] **M5** — `apps/sales/views/ContractSubscriptionManagement/ContractObligations.py:151`: Add `select_related("contract")` in `contract_obligation_edit` to prevent query on `str(obl)`.
- [ ] **M6** — `apps/sales/views/ContractSubscriptionManagement/UsageMeterRecords.py:127`: Add `select_related("subscription")` in `usage_meter_record_edit` to prevent query on `str(meter)`.
- [ ] **M7** — `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:118`: Add `account` to `contract.subscriptions.all().select_related("currency", "account")`.
- [ ] **M8** — `apps/sales/forms/ContractSubscriptionManagement/CustomerSubscriptions.py:116`: Constrain `quantity` in `SubscriptionUpgradeForm` with `max_value=1000000` to prevent Decimal overflow on MRR.
- [ ] **M9** — `apps/sales/forms/ContractSubscriptionManagement/ContractObligations.py:102`: Require `min_value=Decimal("0.01")` on `ObligationBreachForm.penalty_amount`.
- [ ] **M10** — `templates/sales/contractsubscriptionmanagement/boards/contract_subscription_workspace.html:46`: KPI stat card label reads "Active Contract TCV". Update to "Total Contract Value (TCV)".
