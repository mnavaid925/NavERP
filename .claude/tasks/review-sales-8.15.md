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
