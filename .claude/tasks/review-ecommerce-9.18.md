# Review Findings: eCommerce 9.18 Fraud & Risk Management

Base: `15b412c62969da26e5d605a6927a493f35d7e163`
Target: HEAD

---

## Findings Summary
- **Critical**: 1 (1 fixed, 0 open)
- **Important**: 8 (8 fixed, 0 open)
- **Minor**: 8 (8 fixed, 0 open)
- **Total**: 17 (17 fixed, 0 open)

---

## Critical

### [x] C1: `write_audit_log()` Signature Incompatibility Across All 12 Mutating Views
- **Status:** [x] fixed — corrected write_audit_log argument order to (request.user, obj, action, changes, tenant=request.tenant) across all 4 view files and 12 call sites
- **File & Line**:
  - `apps/ecommerce/views/FraudRisk/FraudRules.py`: Lines 128 (`create`), 164 (`edit`), 191 (`delete`)
  - `apps/ecommerce/views/FraudRisk/TransactionRiskAssessments.py`: Lines 94 (`create`), 124 (`edit`), 151 (`delete`)
  - `apps/ecommerce/views/FraudRisk/ChargebackDisputes.py`: Lines 74 (`create`), 120 (`edit`), 147 (`delete`)
  - `apps/ecommerce/views/FraudRisk/AccountSecurityAlerts.py`: Lines 80 (`create`), 126 (`edit`), 153 (`delete`)
- **Problem**:
  Views call `write_audit_log` with keyword arguments `model_name="...", object_id=...`. The signature in `apps/core/utils.py` is `write_audit_log(user, obj, action, changes=None, tenant=None)`. This triggers `TypeError: write_audit_log() got an unexpected keyword argument 'model_name'` (HTTP 500) upon POST form submission or deletion across all 12 mutating endpoints.
- **Fix**:
  Update all 12 call sites to:
  ```python
  write_audit_log(request.user, instance, "create", changes, tenant=request.tenant)
  ```

---

## Important

### [x] I1: Cross-Tenant User Leak in Form Queryset Re-assignment
- **Status:** [x] fixed — preserved tenant scoping on user fields by chaining filter(is_active=True) onto existing tenant-scoped querysets
- **File & Line**: `apps/ecommerce/forms/FraudRisk/TransactionRiskAssessments.py:48-49` & `apps/ecommerce/forms/FraudRisk/AccountSecurityAlerts.py:35-37`
- **Problem**:
  Forms explicitly overwrite `self.fields["user"].queryset = User.objects.filter(is_active=True)`, `analyst_user`, `assigned_investigator`, and `resolved_by` without filtering by `tenant`, stripping `TenantModelForm` tenant scoping and exposing usernames and emails across tenants in dropdowns.
- **Fix**:
  Preserve tenant scoping on user fields:
  ```python
  if self.tenant:
      self.fields["user"].queryset = self.fields["user"].queryset.filter(is_active=True)
      self.fields["analyst_user"].queryset = self.fields["analyst_user"].queryset.filter(is_active=True)
  ```
  (and equivalent in `AccountSecurityAlertForm.__init__`).

### [x] I2: Missing Defense-in-Depth `reject_foreign` Validation in Form `clean()`
- **Status:** [x] fixed — imported reject_foreign and added clean() validation across TransactionRiskAssessmentForm, ChargebackDisputeForm, and AccountSecurityAlertForm
- **File & Line**: `apps/ecommerce/forms/FraudRisk/TransactionRiskAssessments.py:51`, `apps/ecommerce/forms/FraudRisk/ChargebackDisputes.py:41`, `apps/ecommerce/forms/FraudRisk/AccountSecurityAlerts.py:31`
- **Problem**:
  Forms lack secondary server-side `clean()` validation calling `reject_foreign` to prevent foreign tenant PK injection on relations (`order`, `customer_party`, `party`).
- **Fix**:
  Import `reject_foreign` from `apps.ecommerce.forms._common` and call in `clean()` for each form.

### [x] I3: Missing Submodule Package-Level Re-exports and `__all__`
- **Status:** [x] fixed — added re-export blocks and __all__ lists in models/FraudRisk/__init__.py, forms/FraudRisk/__init__.py, and views/FraudRisk/__init__.py
- **File & Line**: `apps/ecommerce/models/FraudRisk/__init__.py:1`, `apps/ecommerce/forms/FraudRisk/__init__.py:1`, `apps/ecommerce/views/FraudRisk/__init__.py:1`
- **Problem**:
  Package-level `__init__.py` files do not re-export their models, forms, or views. Submodule package imports like `from apps.ecommerce.models.FraudRisk import FraudRule` fail with `ImportError`.
- **Fix**:
  Add re-export blocks and `__all__` lists in all three `FraudRisk/__init__.py` files.

### [x] I4: Pagination Links Drop Active Filter Parameters
- **Status:** [x] fixed — appended type, is_active, and action filter query parameters to pagination hrefs in all list templates
- **File & Line**:
  - `templates/ecommerce/fraud_risk/fraud_rule/list.html:203` (drops `type` and `is_active`)
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/list.html:195` (drops `action`)
  - `templates/ecommerce/fraud_risk/account_security_alert/list.html:184` (drops `type`)
- **Problem**:
  Navigating across paginated pages drops active filter selections.
- **Fix**:
  Append missing filter query parameters to pagination hrefs in each list template.

### [x] I5: Non-Existent theme.css Class `text-warning` (L33)
- **Status:** [x] fixed — replaced text-warning with valid theme.css class text-warn in fraud_risk_hub.html and transaction_risk_assessment templates
- **File & Line**:
  - `templates/ecommerce/fraud_risk/fraud_risk_hub.html:124`
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/list.html:113`
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/detail.html:61, 71`
- **Problem**:
  `text-warning` is not defined in `static/css/theme.css` (only `text-warn` is defined) and renders unstyled.
- **Fix**:
  Replace `text-warning` with `text-warn`.

### [x] I6: Non-Existent theme.css Class `text-green` (L33)
- **Status:** [x] fixed — replaced text-green with valid theme.css class text-ok across fraud_risk_hub.html, fraud_rule/list.html, and transaction_risk_assessment templates
- **File & Line**:
  - `templates/ecommerce/fraud_risk/fraud_risk_hub.html:124`
  - `templates/ecommerce/fraud_rule/list.html:139`
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/list.html:113, 121, 122`
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/detail.html:61, 75, 127, 133`
- **Problem**:
  `text-green` is not in `static/css/theme.css` (semantic class is `.text-ok`).
- **Fix**:
  Replace `text-green` with `text-ok`.

### [x] I7: N+1 Query in `fraud_risk_hub` for `party` Relation
- **Status:** [x] fixed — added select_related("user", "party") on recent_alerts in fraud_risk_hub
- **File & Line**: `apps/ecommerce/views/FraudRisk/FraudRules.py:41` & `templates/ecommerce/fraud_risk/fraud_risk_hub.html:230-232`
- **Problem**:
  `recent_alerts = alerts_qs.select_related("user")[:5]` omits `party`, triggering N+1 queries when accessing `item.party.name`.
- **Fix**:
  Update to `recent_alerts = alerts_qs.select_related("user", "party")[:5]`.

### [x] I8: Unconsolidated KPI Count & Sum Queries in `fraud_risk_hub`
- **Status:** [x] fixed — consolidated 11 sequential queries into 4 single aggregate calls using Count(..., filter=Q(...)) and Sum(...)
- **File & Line**: `apps/ecommerce/views/FraudRisk/FraudRules.py:24-38`
- **Problem**:
  Runs 11 sequential queries across 4 models to compute KPI cards instead of 4 consolidated `.aggregate()` queries.
- **Fix**:
  Consolidate stats queries using `Count(..., filter=Q(...))` and `Sum(...)`.

---

## Minor

### [x] M1: Analyst and Resolver Attribution Exposed in Editable Forms
- **Status:** [x] fixed — excluded analyst_user from TransactionRiskAssessmentForm and resolved_by from AccountSecurityAlertForm, updated form templates to display attribution cleanly
- **File & Line**: `apps/ecommerce/forms/FraudRisk/TransactionRiskAssessments.py:37` & `AccountSecurityAlerts.py:27`
- **Problem**:
  `analyst_user` and `resolved_by` are exposed as editable fields in ModelForms.
- **Fix**:
  Exclude from form fields; set attribution strictly in view save paths.

### [x] M2: Badge Fallback Hardcoding
- **Status:** [x] fixed — used get_action_to_take_display and get_status_display in badge fallback branches
- **File & Line**: `templates/ecommerce/fraud_risk/fraud_rule/detail.html:29` & `templates/ecommerce/fraud_risk/account_security_alert/detail.html:36`
- **Problem**:
  `{% else %}` fallback branches hardcode `Allow` and `Dismissed` instead of using `get_FIELD_display`.
- **Fix**:
  Use `{{ rule.get_action_to_take_display }}` and `{{ alert.get_status_display }}`.

### [x] M3: Misleading Stat Card Label in Rule List
- **Status:** [x] fixed — updated stat card label to Showing Rules in fraud rule list
- **File & Line**: `templates/ecommerce/fraud_risk/fraud_rule/list.html:47`
- **Problem**:
  Card label says "Checkout Scope" but displays `{{ rules|length }} Showing`.
- **Fix**:
  Update label to "Showing Rules" or display `active_count`.

### [x] M4: Redundant Count Query in `fraud_rule_list`
- **Status:** [x] fixed — consolidated total_count and active_count queries into a single aggregate call
- **File & Line**: `apps/ecommerce/views/FraudRisk/FraudRules.py:94-95`
- **Problem**:
  Runs `total_count = qs.count()` and `active_count = qs.filter(is_active=True).count()` as two sequential queries.
- **Fix**:
  Consolidate into single `aggregate()` call.

### [x] M5: Guard Nullable User Lookup in Assessment Detail
- **Status:** [x] fixed — wrapped analyst_user lookup in explicit {% if assessment.analyst_user %} block
- **File & Line**: `templates/ecommerce/fraud_risk/transaction_risk_assessment/detail.html:186`
- **Problem**:
  `assessment.analyst_user.username|default:"Unassigned"` lacks an explicit `{% if assessment.analyst_user %}` block.
- **Fix**:
  Wrap in `{% if assessment.analyst_user %}{{ assessment.analyst_user.username }}{% else %}Unassigned{% endif %}`.

### [x] M6: Filter Form Controls Missing Accessible `aria-label` Attributes
- **Status:** [x] fixed — added aria-label attributes to search inputs and filter selects across all 4 list templates
- **File & Line**: `templates/ecommerce/fraud_risk/fraud_rule/list.html`, `transaction_risk_assessment/list.html`, `chargeback_dispute/list.html`, `account_security_alert/list.html`
- **Problem**:
  Search inputs and filter `<select>` tags lack `aria-label` accessibility attributes.
- **Fix**:
  Add `aria-label` attributes to filter inputs and selects.

### [x] M7: RTL Compatibility in Assessment Detail
- **Status:** [x] fixed — replaced physical margin ml-2 with logical margin ms-2 in transaction risk assessment detail
- **File & Line**: `templates/ecommerce/fraud_risk/transaction_risk_assessment/detail.html:146, 148`
- **Problem**:
  Uses `ml-2` instead of logical margin `ms-2`.
- **Fix**:
  Replace `ml-2` with `ms-2`.

### [x] M8: Composite Index on `["tenant", "-created_at"]` for High-Volume Log Models
- **Status:** [x] fixed — added composite indexes on ["tenant", "-created_at"] to TransactionRiskAssessment, ChargebackDispute, and AccountSecurityAlert models; generated and applied migration 0036
- **File & Line**: `apps/ecommerce/models/FraudRisk/TransactionRiskAssessments.py`, `ChargebackDisputes.py`, `AccountSecurityAlerts.py`
- **Problem**:
  Default ordering on `-created_at` in tenant-scoped tables benefits from a composite index `["tenant", "-created_at"]`.
- **Fix**:
  Add `models.Index(fields=["tenant", "-created_at"])` to `Meta.indexes`.
