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


