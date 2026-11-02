# Review Findings: eCommerce 9.18 Fraud & Risk Management

Base: `15b412c62969da26e5d605a6927a493f35d7e163`
Target: HEAD

---

## Findings Summary
- **Critical**: 1
- **Important**: 8
- **Minor**: 8
- **Total**: 17

---

## Critical

### [ ] C1: `write_audit_log()` Signature Incompatibility Across All 12 Mutating Views
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

### [ ] I1: Cross-Tenant User Leak in Form Queryset Re-assignment
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

### [ ] I2: Missing Defense-in-Depth `reject_foreign` Validation in Form `clean()`
- **File & Line**: `apps/ecommerce/forms/FraudRisk/TransactionRiskAssessments.py:51`, `apps/ecommerce/forms/FraudRisk/ChargebackDisputes.py:41`, `apps/ecommerce/forms/FraudRisk/AccountSecurityAlerts.py:31`
- **Problem**:
  Forms lack secondary server-side `clean()` validation calling `reject_foreign` to prevent foreign tenant PK injection on relations (`order`, `customer_party`, `party`).
- **Fix**:
  Import `reject_foreign` from `apps.ecommerce.forms._common` and call in `clean()` for each form.

### [ ] I3: Missing Submodule Package-Level Re-exports and `__all__`
- **File & Line**: `apps/ecommerce/models/FraudRisk/__init__.py:1`, `apps/ecommerce/forms/FraudRisk/__init__.py:1`, `apps/ecommerce/views/FraudRisk/__init__.py:1`
- **Problem**:
  Package-level `__init__.py` files do not re-export their models, forms, or views. Submodule package imports like `from apps.ecommerce.models.FraudRisk import FraudRule` fail with `ImportError`.
- **Fix**:
  Add re-export blocks and `__all__` lists in all three `FraudRisk/__init__.py` files.

### [ ] I4: Pagination Links Drop Active Filter Parameters
- **File & Line**:
  - `templates/ecommerce/fraud_risk/fraud_rule/list.html:203` (drops `type` and `is_active`)
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/list.html:195` (drops `action`)
  - `templates/ecommerce/fraud_risk/account_security_alert/list.html:184` (drops `type`)
- **Problem**:
  Navigating across paginated pages drops active filter selections.
- **Fix**:
  Append missing filter query parameters to pagination hrefs in each list template.

### [ ] I5: Non-Existent theme.css Class `text-warning` (L33)
- **File & Line**:
  - `templates/ecommerce/fraud_risk/fraud_risk_hub.html:124`
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/list.html:113`
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/detail.html:61, 71`
- **Problem**:
  `text-warning` is not defined in `static/css/theme.css` (only `text-warn` is defined) and renders unstyled.
- **Fix**:
  Replace `text-warning` with `text-warn`.

### [ ] I6: Non-Existent theme.css Class `text-green` (L33)
- **File & Line**:
  - `templates/ecommerce/fraud_risk/fraud_risk_hub.html:124`
  - `templates/ecommerce/fraud_rule/list.html:139`
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/list.html:113, 121, 122`
  - `templates/ecommerce/fraud_risk/transaction_risk_assessment/detail.html:61, 75, 127, 133`
- **Problem**:
  `text-green` is not in `static/css/theme.css` (semantic class is `.text-ok`).
- **Fix**:
  Replace `text-green` with `text-ok`.

### [ ] I7: N+1 Query in `fraud_risk_hub` for `party` Relation
- **File & Line**: `apps/ecommerce/views/FraudRisk/FraudRules.py:41` & `templates/ecommerce/fraud_risk/fraud_risk_hub.html:230-232`
- **Problem**:
  `recent_alerts = alerts_qs.select_related("user")[:5]` omits `party`, triggering N+1 queries when accessing `item.party.name`.
- **Fix**:
  Update to `recent_alerts = alerts_qs.select_related("user", "party")[:5]`.

### [ ] I8: Unconsolidated KPI Count & Sum Queries in `fraud_risk_hub`
- **File & Line**: `apps/ecommerce/views/FraudRisk/FraudRules.py:24-38`
- **Problem**:
  Runs 11 sequential queries across 4 models to compute KPI cards instead of 4 consolidated `.aggregate()` queries.
- **Fix**:
  Consolidate stats queries using `Count(..., filter=Q(...))` and `Sum(...)`.

---

## Minor

### [ ] M1: Analyst and Resolver Attribution Exposed in Editable Forms
- **File & Line**: `apps/ecommerce/forms/FraudRisk/TransactionRiskAssessments.py:37` & `AccountSecurityAlerts.py:27`
- **Problem**:
  `analyst_user` and `resolved_by` are exposed as editable fields in ModelForms.
- **Fix**:
  Exclude from form fields; set attribution strictly in view save paths.

### [ ] M2: Badge Fallback Hardcoding
- **File & Line**: `templates/ecommerce/fraud_risk/fraud_rule/detail.html:29` & `templates/ecommerce/fraud_risk/account_security_alert/detail.html:36`
- **Problem**:
  `{% else %}` fallback branches hardcode `Allow` and `Dismissed` instead of using `get_FIELD_display`.
- **Fix**:
  Use `{{ rule.get_action_to_take_display }}` and `{{ alert.get_status_display }}`.

### [ ] M3: Misleading Stat Card Label in Rule List
- **File & Line**: `templates/ecommerce/fraud_risk/fraud_rule/list.html:47`
- **Problem**:
  Card label says "Checkout Scope" but displays `{{ rules|length }} Showing`.
- **Fix**:
  Update label to "Showing Rules" or display `active_count`.

### [ ] M4: Redundant Count Query in `fraud_rule_list`
- **File & Line**: `apps/ecommerce/views/FraudRisk/FraudRules.py:94-95`
- **Problem**:
  Runs `total_count = qs.count()` and `active_count = qs.filter(is_active=True).count()` as two sequential queries.
- **Fix**:
  Consolidate into single `aggregate()` call.

### [ ] M5: Guard Nullable User Lookup in Assessment Detail
- **File & Line**: `templates/ecommerce/fraud_risk/transaction_risk_assessment/detail.html:186`
- **Problem**:
  `assessment.analyst_user.username|default:"Unassigned"` lacks an explicit `{% if assessment.analyst_user %}` block.
- **Fix**:
  Wrap in `{% if assessment.analyst_user %}{{ assessment.analyst_user.username }}{% else %}Unassigned{% endif %}`.

### [ ] M6: Filter Form Controls Missing Accessible `aria-label` Attributes
- **File & Line**: `templates/ecommerce/fraud_risk/fraud_rule/list.html`, `transaction_risk_assessment/list.html`, `chargeback_dispute/list.html`, `account_security_alert/list.html`
- **Problem**:
  Search inputs and filter `<select>` tags lack `aria-label` accessibility attributes.
- **Fix**:
  Add `aria-label` attributes to filter inputs and selects.

### [ ] M7: RTL Compatibility in Assessment Detail
- **File & Line**: `templates/ecommerce/fraud_risk/transaction_risk_assessment/detail.html:146, 148`
- **Problem**:
  Uses `ml-2` instead of logical margin `ms-2`.
- **Fix**:
  Replace `ml-2` with `ms-2`.

### [ ] M8: Composite Index on `["tenant", "-created_at"]` for High-Volume Log Models
- **File & Line**: `apps/ecommerce/models/FraudRisk/TransactionRiskAssessments.py`, `ChargebackDisputes.py`, `AccountSecurityAlerts.py`
- **Problem**:
  Default ordering on `-created_at` in tenant-scoped tables benefits from a composite index `["tenant", "-created_at"]`.
- **Fix**:
  Add `models.Index(fields=["tenant", "-created_at"])` to `Meta.indexes`.
