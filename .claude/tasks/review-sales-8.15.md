# Review Findings: Sub-module 8.15 Contract & Subscription Management

**Base Commit**: `f64118d1453d8b4e05181cf64ba89d9a95ddb49f`
**Target App**: `apps/sales/` (Sub-module 8.15)
**Date**: 2026-10-22

---

## 1. Code Reviewer Findings

### Verdict
Sub-module 8.15 is comprehensively architected with exemplary tenant isolation and Core spine reuse, but contains one critical crash bug in CPQ renewal quote generation and minor validation/dead-code discrepancies.

### Findings
- **[CRITICAL]** `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:213`: `customer_contract_generate_renewal_quote` instantiates `CPQQuote.objects.create` with non-existent field arguments `title=` (CPQQuote defines `name`) and `grand_total=` (CPQQuote defines `total`), raising an immediate 500 `TypeError` upon execution. Fix: Replace `title=f"Renewal Quote for {contract.title}"` with `name=f"Renewal Quote for {contract.title}"` and replace `grand_total=renewal_amount` with `total=renewal_amount`.
- **[IMPORTANT]** `apps/sales/models/ContractSubscriptionManagement/ContractObligations.py:117`: `clean()` fails to enforce relational consistency between `subscription` and `contract`, allowing an obligation to reference a subscription belonging to a different contract. Fix: Add `if self.subscription_id and self.subscription.contract_id and self.subscription.contract_id != self.contract_id: raise ValidationError({"subscription": "Subscription must belong to the selected contract."})`.
- **[IMPORTANT]** `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:202`: State-mutating and quote-generating actions `customer_contract_generate_renewal_quote` and `customer_contract_execute_auto_renew` perform database mutations and write audit logs without transaction boundaries. Fix: Decorate with `@transaction.atomic`.
- **[IMPORTANT]** `apps/sales/views/ContractSubscriptionManagement/ContractSubscriptionWorkspaces.py:52`: `urgent_contracts` checks `hasattr(contracts_qs, "order_date")` (which is never true for QuerySets) and conditionally duplicates the entire query chain with a non-existent method call. Fix: Simplify to `urgent_contracts = contracts_qs.filter(status="active", end_date__gte=today, end_date__lte=in_60_days).select_related("account", "owner").order_by("end_date")[:5]`.
- **[MINOR]** `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:13`: `tenant_admin_required` is imported from `apps.core.decorators` but left unused. Fix: Remove the unused import or apply it to `customer_contract_delete`.
- **[MINOR]** `templates/sales/contractsubscriptionmanagement/customersubscription/list.html:54`: KPI stat card is labeled "Total Annualized ARR" but renders `${{ total_mrr|floatformat:2|default:"0" }} / mo`. Fix: Rename label to "Monthly Recurring Revenue (MRR)" or pass annualized `total_arr` from view context.
- **[MINOR]** `apps/sales/forms/ContractSubscriptionManagement/CustomerContracts.py:65`: `account` queryset in form allows selecting any tenant party rather than narrowing to customer role. Fix: Filter with `Party.objects.filter(tenant=self.tenant, roles__role="customer").distinct()`.

### Done Well
Strict multi-tenancy and Core spine adherence — zero duplicate customer, quote, order, user, currency, or platform subscription tables were introduced, and every model and query correctly enforces `tenant` isolation and `TenantNumbered` constraints.

### Suggested Tests
- `test_customer_contract_generate_renewal_quote_creates_cpq_quote_with_name_and_total`
- `test_contract_obligation_clean_rejects_foreign_subscription_contract`
- `test_customer_contract_execute_auto_renew_applies_uplift_and_term_extension`
- `test_customer_subscription_mrr_normalization`
- `test_usage_meter_record_charge_calculation`
- `test_workspace_and_renewal_radar_render_cleanly`

---

## 2. Explorer Findings

### Verdict
Sub-module 8.15 demonstrates clean architectural integration with the core spine and 100% route/export completeness, but contains a runtime TypeError when generating renewal quotes and a missing cross-model contract validation check on obligations.

### Findings
- **[CRITICAL]** `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:210`: `CPQQuote.objects.create()` is passed `title=...` and `grand_total=...`, but `CPQQuote` defines `name` (not `title`) and `total` (not `grand_total`). Invoking the `customer_contract_generate_renewal_quote` view crashes with `TypeError: CPQQuote() got an unexpected keyword argument 'title'`. Fix: Pass `name=f"Renewal Quote for {contract.title}"`, `total=renewal_amount`, and remove `grand_total`.
- **[IMPORTANT]** `apps/sales/models/ContractSubscriptionManagement/ContractObligations.py:113`: `ContractObligation.clean()` validates tenant isolation but omits cross-model contract check when `subscription` is set: `"When subscription is provided and has contract, assert subscription.contract_id == self.contract_id"`. Fix: Add `if self.subscription_id and self.subscription.contract_id and self.subscription.contract_id != self.contract_id: raise ValidationError({"subscription": "Associated subscription must belong to the selected contract."})`.
- **[IMPORTANT]** `apps/sales/views/ContractSubscriptionManagement/ContractSubscriptionWorkspaces.py:52`: `urgent_contracts` uses an invalid fallback ternary `...order_date() if hasattr(contracts_qs, "order_date") else ...order_by("end_date")[:5]`. Fix: Simplify to direct `contracts_qs.filter(status="active", end_date__gte=today, end_date__lte=in_60_days).select_related("account", "owner").order_by("end_date")[:5]`.
- **[MINOR]** `templates/sales/contractsubscriptionmanagement/customersubscription/list.html:63`: The list filter grid omits the `account` select dropdown even though `CustomerSubscriptionFilterForm` defines `account` and `customer_subscription_list` processes it. Fix: Add the `account` select element to the filter form grid.
- **[MINOR]** `templates/sales/contractsubscriptionmanagement/customercontract/list.html:63`: The contract filter grid omits the `owner` dropdown defined in `CustomerContractFilterForm`. Fix: Add the `owner` dropdown to the contract list filter bar.
- **[MINOR]** `templates/sales/contractsubscriptionmanagement/boards/contract_subscription_workspace.html:106`: The view calculates and passes `urgent_subscriptions` in context, but the template only renders tables for `urgent_contracts` and `at_risk_obligations`. Fix: Add an `urgent_subscriptions` table widget to the dashboard layout.

---

## 3. Frontend Reviewer Findings

### Verdict
All 14 templates for Sub-module 8.15 exhibit high quality and strong adherence to NavERP design standards, with clean layout structure, complete CRUD actions, zero comment leaks, and correct color-named badges, with only minor filter omissions and KPI label adjustments required.

### Findings
- **[IMPORTANT]** `templates/sales/contractsubscriptionmanagement/customersubscription/list.html:63`: Filter completeness omission: `CustomerSubscriptionFilterForm` and `customer_subscription_list` view define and process an `account` filter, but the template omits the `account` select dropdown from the filter bar. Fix: Add an `account` `<select>` dropdown populated from `filter_form.fields.account.queryset` with `{% if request.GET.account == acc.pk|stringformat:"d" %}selected{% endif %}`.
- **[IMPORTANT]** `templates/sales/contractsubscriptionmanagement/contractobligation/list.html:59`: Filter completeness omission: `ContractObligationFilterForm` and `contract_obligation_list` view define and process an `assigned_to` filter, but the template omits the `assigned_to` select dropdown from the filter bar. Fix: Add an `assigned_to` `<select>` dropdown populated from `filter_form.fields.assigned_to.queryset` with `{% if request.GET.assigned_to == u.pk|stringformat:"d" %}selected{% endif %}`.
- **[IMPORTANT]** `templates/sales/contractsubscriptionmanagement/customersubscription/list.html:54`: Misleading KPI stat card metric: The stat card header displays "Total Annualized ARR", but the value rendered is `${{ total_mrr|floatformat:2|default:"0" }} / mo`. Fix: Pass `total_arr = (total_mrr * Decimal("12.00")).quantize(Decimal("0.01"))` in the view context and render `${{ total_arr|floatformat:2 }}`, or update the card label to reflect Monthly Recurring Revenue.
- **[MINOR]** `templates/sales/contractsubscriptionmanagement/contractobligation/list.html:28` & `templates/sales/contractsubscriptionmanagement/boards/renewal_automation_dashboard.html:32`: Non-standard stat-icon color `<div class="stat-icon red">` is used for alert cards. Fix: Use `stat-icon orange` for consistency with system guidelines.
- **[MINOR]** `templates/sales/contractsubscriptionmanagement/usagemeterrecord/detail.html:180`: None-safe display convention: `{{ usage_record.subscription.plan_code }}` is rendered without a fallback default filter. Fix: Add `|default:"—"`.

---

## 4. Performance Reviewer Findings

### Verdict
The Sub-module 8.15 ORM implementation is well-structured with proper pagination ordering and baseline index coverage, but suffers from chained N+1 query storms in form rendering through `CustomerSubscription.__str__`, redundant sequential count queries across executive dashboards, template `.count` bypasses of evaluated queryset caches, and missed compound indexes for high-frequency horizon scans.

### Findings
- **[CRITICAL]** `apps/sales/forms/ContractSubscriptionManagement/UsageMeterRecords.py:44`: Chained N+1 query vulnerability through `CustomerSubscription.__str__` (L18). In `UsageMeterRecordForm.__init__`, `self.fields["subscription"].queryset` lacks `.select_related("account")`. Because `CustomerSubscription.__str__` accesses `self.account.name`, rendering `<select name="subscription">` triggers 1 + N queries against `core_party`. Fix: Add `.select_related("account")`.
- **[CRITICAL]** `apps/sales/forms/ContractSubscriptionManagement/ContractObligations.py:53`: Chained N+1 query vulnerability through `CustomerSubscription.__str__` (L18). In `ContractObligationForm.__init__`, `self.fields["subscription"].queryset` lacks `.select_related("account")`. Fix: Add `.select_related("account")`.
- **[IMPORTANT]** `apps/sales/views/ContractSubscriptionManagement/ContractSubscriptionWorkspaces.py:25`: Fragmented aggregation round-trips. Consolidate 4 `CustomerContract` queries (`active_count`, `total_tcv`, `expiring_30`, `expiring_60`) and 2 `ContractObligation` queries (`total`, `fulfilled`) into unified conditional aggregates.
- **[IMPORTANT]** `apps/sales/views/ContractSubscriptionManagement/RenewalAutomations.py:24`: Combine 3 sequential count queries for renewal horizon buckets (`exp_30`, `exp_60`, `exp_90`) into a single `contracts_qs.aggregate(...)` call with conditional `Count("id", filter=Q(...))`.
- **[IMPORTANT]** `apps/sales/views/ContractSubscriptionManagement/RenewalAutomations.py:40`: In-memory Python loop deriving financial KPI. Replace row iteration with ORM `Sum(...)` aggregation over `annual_contract_value` / `total_contract_value` and `price_uplift_pct`.
- **[IMPORTANT]** `apps/sales/views/ContractSubscriptionManagement/RenewalAutomations.py:33`: Redundant table scan for `auto_renew_candidates`. Filter the already evaluated `upcoming_renewals` list in Python: `[c for c in upcoming_renewals if c.auto_renew]`.
- **[IMPORTANT]** `apps/sales/views/ContractSubscriptionManagement/ContractSubscriptionWorkspaces.py:58`: Dead query execution. `urgent_subscriptions` executes against DB but is never rendered in template. Fix: Either render table in template or eliminate query.
- **[IMPORTANT]** `templates/sales/contractsubscriptionmanagement/boards/renewal_automation_dashboard.html:76,144`: Template `.count` triggers redundant SQL queries on evaluated QuerySets. Replace `{{ auto_renew_candidates.count }}` and `{{ upcoming_renewals.count }}` with `|length`.
- **[IMPORTANT]** `templates/sales/contractsubscriptionmanagement/customercontract/detail.html:150,216` & `templates/sales/contractsubscriptionmanagement/customersubscription/detail.html:218,286`: Replace related manager `.count` calls (`subscriptions.count`, `obligations.count`, `usage_records.count`) with `|length` to reuse Django's evaluated queryset cache.
- **[IMPORTANT]** `apps/sales/models/ContractSubscriptionManagement/CustomerContracts.py:128` & `CustomerSubscriptions.py:122` & `ContractObligations.py:103`: Missing compound indexes on multi-column filter targets. Add `Index(fields=["tenant", "status", "end_date"], name="sales_cct_ten_stat_end_idx")` to CustomerContract, `Index(fields=["tenant", "contract"], name="sales_csb_ten_contract_idx")` to CustomerSubscription, and `Index(fields=["tenant", "subscription"], name="sales_obl_ten_sub_idx")` to ContractObligation.
- **[MINOR]** `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:56`: Combine `total_tcv` and `active_count` in `customer_contract_list` into a single aggregate query.
- **[MINOR]** `apps/sales/views/ContractSubscriptionManagement/CustomerSubscriptions.py:63`: Combine `total_mrr` and `active_count` in `customer_subscription_list` into a single aggregate query.
- **[MINOR]** `apps/sales/views/ContractSubscriptionManagement/ContractObligations.py:151`: Add `select_related("contract")` in `contract_obligation_edit` to prevent extra query on `str(obl)`.
- **[MINOR]** `apps/sales/views/ContractSubscriptionManagement/UsageMeterRecords.py:127`: Add `select_related("subscription")` in `usage_meter_record_edit` to prevent extra query on `str(meter)`.
- **[MINOR]** `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:118`: Add `account` to `contract.subscriptions.all().select_related("currency", "account")`.

---

## 5. QA Smoke Tester Findings

### Verdict
Sub-module 8.15 exhibits flawless multi-tenant IDOR protection (100% 404 enforcement across all foreign tenant record requests) and 100% operational read/GET views across all dashboards, list views, detail views, and edit/create pages; however, runtime execution revealed two critical defects: an invalid keyword crash when instantiating `CPQQuote` in renewal quote generation (`TypeError: CPQQuote() got unexpected keyword arguments: 'title', 'grand_total'`), and a universal crash on every mutating POST action due to incompatible arguments passed to `write_audit_log` (`TypeError: write_audit_log() got an unexpected keyword argument 'model_name'`).

### Findings
- **[CRITICAL]** `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:84,138,167,188,222,254`, `CustomerSubscriptions.py:93,161,190,210,230,256,279`, `UsageMeterRecords.py:77,134,163,183,203`, `ContractObligations.py:92,156,185,208,233`: All 21 `write_audit_log` call sites pass invalid keyword arguments `(tenant=..., user=..., action=..., model_name=..., object_id=..., object_repr=...)`. In `apps/core/utils.py`, the authoritative signature is `write_audit_log(user, obj, action, changes=None, tenant=None)`. Calling any mutating action causes an immediate `TypeError: write_audit_log() got an unexpected keyword argument 'model_name'`. Fix: Refactor all call sites across all 4 view files to standard signature `write_audit_log(user=request.user, obj=instance, action=action, tenant=tenant)`.
- **[CRITICAL]** `apps/sales/views/ContractSubscriptionManagement/CustomerContracts.py:210`: View `customer_contract_generate_renewal_quote` crashes with `TypeError: CPQQuote() got unexpected keyword arguments: 'title', 'grand_total'`. Fix: Change `title=...` to `name=...` and `grand_total=...` to `total=...`.
- **[IMPORTANT]** `apps/sales/forms/ContractSubscriptionManagement/CustomerSubscriptions.py:27`: `renewal_notice_days` has no default fallback if omitted from client post data, causing form validation failure on bare POST requests. Fix: Ensure `renewal_notice_days` has initial default of `30` in form `__init__`.
- **[MINOR]** `templates/sales/contractsubscriptionmanagement/boards/renewal_automation_dashboard.html:76,144`: Section table headers render "Upcoming Renewal Candidates (60 Days)" and "Auto-Renew Executable Contracts (30 Days)" instead of exact spec labels.
- **[MINOR]** `templates/sales/contractsubscriptionmanagement/boards/contract_subscription_workspace.html:46`: KPI stat card label reads "Active Contract TCV" rather than "Total Contract Value".




