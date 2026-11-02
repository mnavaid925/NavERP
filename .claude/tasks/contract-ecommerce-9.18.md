# Contract — Sub-module 9.18: Fraud & Risk Management (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.18 Fraud & Risk Management · **Module:** 9 eCommerce Management System · **App:** `apps/ecommerce`
- **Date:** 2026-11-02 · **Status:** FROZEN PRE-BUILD CONTRACT · **Phase:** 3.1 Spec
- **App Status:** Extending existing `apps/ecommerce/`. Next incremental migration: `0035_...`
- **Package Layout:** `FraudRisk/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/ecommerce/fraud_risk/`.

---

## 1. Models & CHOICES Contract

All top-level models inherit from `apps.ecommerce.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `FraudRule` (`apps/ecommerce/models/FraudRisk/FraudRules.py`)
- **Table:** `ecommerce_fraud_rule`
- **Number Prefix:** `EFRR` (`EFRR-00001`)
- **CHOICES:**
  - `RULE_SCOPE_CHOICES = [('checkout', 'Checkout / Payment'), ('account_login', 'Account Login'), ('registration', 'Account Registration'), ('promotion', 'Coupon / Promotion Redemption')]`
  - `RULE_TYPE_CHOICES = [('velocity_orders', 'Order Velocity (Orders / Hour)'), ('velocity_cards', 'Card Attempt Velocity'), ('amount_threshold', 'High Order Amount Threshold'), ('avs_cvv_mismatch', 'AVS / CVV Failure'), ('ip_proxy_vpn', 'Proxy / VPN / TOR Detection'), ('country_mismatch', 'Billing / IP Country Mismatch'), ('email_domain_risk', 'High-Risk Disposable Email Domain'), ('blacklist_match', 'Blacklist Entity Match'), ('whitelist_match', 'Whitelist Entity Match')]`
  - `CONDITION_OPERATOR_CHOICES = [('gt', 'Greater Than (>)'), ('gte', 'Greater Than or Equal (>=)'), ('lt', 'Less Than (<)'), ('lte', 'Less Than or Equal (<=)'), ('equals', 'Equals (==)'), ('contains', 'Contains'), ('in_list', 'In Blacklist / Whitelist')]`
  - `ACTION_CHOICES = [('allow', 'Allow / Trust'), ('flag_review', 'Flag for Manual Review'), ('challenge_3ds', 'Challenge (3D Secure / MFA)'), ('block', 'Block / Reject')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=255, help_text="Human-readable rule name")`
  - `rule_code`: `CharField(max_length=50, blank=True, default="", help_text="Unique identifier rule code, e.g. R-VEL-01")`
  - `rule_scope`: `CharField(max_length=30, choices=RULE_SCOPE_CHOICES, default='checkout')`
  - `rule_type`: `CharField(max_length=40, choices=RULE_TYPE_CHOICES, default='velocity_orders')`
  - `condition_operator`: `CharField(max_length=20, choices=CONDITION_OPERATOR_CHOICES, default='gt')`
  - `threshold_value`: `CharField(max_length=255, help_text="Numeric limit, threshold count, or comma-separated match values")`
  - `risk_score_impact`: `IntegerField(default=20, help_text="Risk points added (or subtracted if whitelist) when triggered")`
  - `action_to_take`: `CharField(max_length=25, choices=ACTION_CHOICES, default='flag_review')`
  - `priority`: `IntegerField(default=10, help_text="Execution order (lower runs first)")`
  - `is_active`: `BooleanField(default=True)`
  - `description`: `TextField(blank=True, default="")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_efrr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'is_active', 'priority'], name='idx_efrr_ten_act_prio')`
  - `Index(fields=['tenant', 'rule_scope'], name='idx_efrr_ten_scope')`
  - `Index(fields=['tenant', 'rule_type'], name='idx_efrr_ten_type')`
- **Ordering:** `['priority', 'name']`

---

### 1.2 `TransactionRiskAssessment` (`apps/ecommerce/models/FraudRisk/TransactionRiskAssessments.py`)
- **Table:** `ecommerce_transaction_risk_assessment`
- **Number Prefix:** `ETRA` (`ETRA-00001`)
- **CHOICES:**
  - `RISK_TIER_CHOICES = [('low', 'Low Risk (0-25)'), ('medium', 'Medium Risk (26-60)'), ('high', 'High Risk (61-85)'), ('critical', 'Critical Risk (86-100)')]`
  - `RECOMMENDED_ACTION_CHOICES = [('approve', 'Approve'), ('review', 'Manual Review'), ('challenge', 'Challenge (3DS)'), ('reject', 'Reject / Decline')]`
  - `ACTUAL_DECISION_CHOICES = [('pending', 'Pending Assessment'), ('approved_auto', 'Auto-Approved'), ('approved_manual', 'Approved by Analyst'), ('declined_auto', 'Auto-Declined'), ('declined_manual', 'Declined by Analyst'), ('challenged', 'Challenged / 3DS Required')]`
  - `AVS_RESULT_CHOICES = [('match', 'Full Address & Zip Match'), ('partial', 'Partial Match (Zip or Street only)'), ('no_match', 'No Match'), ('not_checked', 'Not Checked / Unsupported')]`
  - `CVV_RESULT_CHOICES = [('match', 'CVV Match'), ('no_match', 'CVV No Match'), ('not_provided', 'Not Provided'), ('not_checked', 'Not Checked')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', null=True, blank=True, on_delete=SET_NULL, related_name='risk_assessments')`
  - `customer_party`: `ForeignKey('core.Party', null=True, blank=True, on_delete=SET_NULL, related_name='fraud_assessments')`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='ecommerce_risk_assessments')`
  - `transaction_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=PROTECT, related_name='fraud_assessments')`
  - `risk_score`: `IntegerField(default=0, help_text="Composite risk score from 0 (very low risk) to 100 (critical fraud risk)")`
  - `risk_tier`: `CharField(max_length=20, choices=RISK_TIER_CHOICES, default='low')`
  - `recommended_action`: `CharField(max_length=25, choices=RECOMMENDED_ACTION_CHOICES, default='approve')`
  - `actual_decision`: `CharField(max_length=25, choices=ACTUAL_DECISION_CHOICES, default='pending')`
  - `avs_result_code`: `CharField(max_length=20, choices=AVS_RESULT_CHOICES, default='not_checked')`
  - `cvv_result_code`: `CharField(max_length=20, choices=CVV_RESULT_CHOICES, default='not_checked')`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `billing_country`: `CharField(max_length=2, blank=True, default="")`
  - `ip_country`: `CharField(max_length=2, blank=True, default="")`
  - `is_geo_mismatch`: `BooleanField(default=False)`
  - `is_proxy_or_vpn`: `BooleanField(default=False)`
  - `device_fingerprint`: `CharField(max_length=128, blank=True, default="")`
  - `velocity_count_24h`: `IntegerField(default=1)`
  - `risk_factors_summary`: `TextField(blank=True, default="", help_text="Summary of triggered rules and signals")`
  - `analyst_user`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='reviewed_risk_assessments')`
  - `analyst_notes`: `TextField(blank=True, default="")`
  - `reviewed_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_etra_tenant_num_uniq')`
  - `Index(fields=['tenant', 'risk_tier'], name='idx_etra_ten_tier')`
  - `Index(fields=['tenant', 'actual_decision'], name='idx_etra_ten_dec')`
  - `Index(fields=['tenant', 'order'], name='idx_etra_ten_order')`
  - `Index(fields=['tenant', 'customer_party'], name='idx_etra_ten_party')`
- **Ordering:** `['-created_at']`

---

### 1.3 `ChargebackDispute` (`apps/ecommerce/models/FraudRisk/ChargebackDisputes.py`)
- **Table:** `ecommerce_chargeback_dispute`
- **Number Prefix:** `ECBD` (`ECBD-00001`)
- **CHOICES:**
  - `PAYMENT_METHOD_CHOICES = [('credit_card', 'Credit Card'), ('debit_card', 'Debit Card'), ('paypal', 'PayPal'), ('bank_transfer', 'Direct Debit / ACH'), ('other', 'Other')]`
  - `REASON_CATEGORY_CHOICES = [('fraudulent', 'Fraudulent / Unauthorized Transaction'), ('unrecognized', 'Unrecognized Card Charge'), ('product_not_received', 'Merchandise / Service Not Received'), ('not_as_described', 'Significantly Not as Described / Defective'), ('credit_not_processed', 'Credit / Refund Not Processed'), ('duplicate_charge', 'Duplicate Processing'), ('subscription_canceled', 'Subscription Canceled Prior to Charge'), ('other', 'Other General Dispute')]`
  - `STAGE_CHOICES = [('inquiry', 'Pre-Dispute Inquiry / Retrieval Request'), ('needs_response', 'Dispute Received - Action Required'), ('under_review', 'Evidence Collation Under Review'), ('representment_submitted', 'Representment Evidence Submitted'), ('won', 'Resolved: Dispute Won'), ('lost', 'Resolved: Dispute Lost'), ('accepted', 'Dispute Accepted (Conceded)')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `order`: `ForeignKey('ecommerce.EcommerceOrder', on_delete=PROTECT, related_name='chargeback_disputes')`
  - `customer_party`: `ForeignKey('core.Party', null=True, blank=True, on_delete=SET_NULL, related_name='customer_disputes')`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=PROTECT, related_name='disputes')`
  - `dispute_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `dispute_fee`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('15.00'), help_text="Payment scheme non-refundable dispute fee")`
  - `gateway_dispute_id`: `CharField(max_length=100, blank=True, default="", help_text="Processor/Gateway external dispute ID")`
  - `payment_method_type`: `CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='credit_card')`
  - `card_brand`: `CharField(max_length=30, blank=True, default="")`
  - `reason_category`: `CharField(max_length=35, choices=REASON_CATEGORY_CHOICES, default='fraudulent')`
  - `reason_code`: `CharField(max_length=30, blank=True, default="", help_text="Card network reason code e.g. 10.4, 4837")`
  - `stage`: `CharField(max_length=30, choices=STAGE_CHOICES, default='needs_response')`
  - `evidence_due_date`: `DateField(null=True, blank=True)`
  - `evidence_summary`: `TextField(blank=True, default="", help_text="Summary of collated evidence (tracking, delivery signature, communications)")`
  - `representment_notes`: `TextField(blank=True, default="", help_text="Formal rebuttal statement submitted to processor")`
  - `representment_submitted_at`: `DateTimeField(null=True, blank=True)`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `outcome_notes`: `TextField(blank=True, default="")`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_ecbd_tenant_num_uniq')`
  - `Index(fields=['tenant', 'stage'], name='idx_ecbd_ten_stage')`
  - `Index(fields=['tenant', 'reason_category'], name='idx_ecbd_ten_reason')`
  - `Index(fields=['tenant', 'order'], name='idx_ecbd_ten_order')`
- **Ordering:** `['-created_at']`

---

### 1.4 `AccountSecurityAlert` (`apps/ecommerce/models/FraudRisk/AccountSecurityAlerts.py`)
- **Table:** `ecommerce_account_security_alert`
- **Number Prefix:** `EASA` (`EASA-00001`)
- **CHOICES:**
  - `ALERT_TYPE_CHOICES = [('credential_stuffing', 'Credential Stuffing Attack Spike'), ('brute_force', 'Brute-Force Password Attempts'), ('suspicious_login', 'Suspicious / New Device Login'), ('impossible_travel', 'Impossible Travel (Geo Velocity)'), ('session_hijack', 'Session / User-Agent Anomaly'), ('sanctions_screening_hit', 'Sanctions List Potential Match'), ('pep_screening_hit', 'Politically Exposed Person (PEP) Match'), ('aml_velocity_alert', 'Anti-Money Laundering (AML) Velocity Spike'), ('excessive_refunds', 'Refund / Voucher Abuse Pattern')]`
  - `SEVERITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')]`
  - `STATUS_CHOICES = [('new', 'New / Unassigned'), ('investigating', 'Under Investigation'), ('resolved_legitimate', 'Resolved: Legitimate Activity'), ('confirmed_threat', 'Confirmed Security Threat'), ('dismissed', 'False Positive / Dismissed')]`
  - `AUTOMATED_ACTION_CHOICES = [('none', 'None / Log Only'), ('force_password_reset', 'Forced Password Reset'), ('lock_account', 'Account Locked'), ('terminate_sessions', 'Active Sessions Terminated'), ('challenge_mfa', 'Step-Up MFA Challenge Triggered'), ('notify_user', 'Security Email Alert Sent')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='account_security_alerts')`
  - `party`: `ForeignKey('core.Party', null=True, blank=True, on_delete=SET_NULL, related_name='security_alerts')`
  - `alert_type`: `CharField(max_length=35, choices=ALERT_TYPE_CHOICES, default='suspicious_login')`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='new')`
  - `automated_action_taken`: `CharField(max_length=35, choices=AUTOMATED_ACTION_CHOICES, default='none')`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True)`
  - `location_info`: `CharField(max_length=150, blank=True, default="")`
  - `user_agent`: `CharField(max_length=255, blank=True, default="")`
  - `incident_details`: `TextField(blank=True, default="")`
  - `assigned_investigator`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='assigned_security_alerts')`
  - `investigation_notes`: `TextField(blank=True, default="")`
  - `resolved_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name='resolved_security_alerts')`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='ecommerce_easa_tenant_num_uniq')`
  - `Index(fields=['tenant', 'alert_type'], name='idx_easa_ten_type')`
  - `Index(fields=['tenant', 'severity'], name='idx_easa_ten_sev')`
  - `Index(fields=['tenant', 'status'], name='idx_easa_ten_stat')`
- **Ordering:** `['-created_at']`

---

## 2. Forms Contract

All forms inherit from `forms.ModelForm` and enforce `tenant`-scoped FK querysets in `__init__`.

### 2.1 `FraudRuleForm` (`apps/ecommerce/forms/FraudRisk/FraudRules.py`)
- **Model:** `FraudRule`
- **Exclude:** `['tenant', 'number', 'created_at', 'updated_at']`
- **Fields:** `['name', 'rule_code', 'rule_scope', 'rule_type', 'condition_operator', 'threshold_value', 'risk_score_impact', 'action_to_take', 'priority', 'is_active', 'description']`

### 2.2 `TransactionRiskAssessmentForm` (`apps/ecommerce/forms/FraudRisk/TransactionRiskAssessments.py`)
- **Model:** `TransactionRiskAssessment`
- **Exclude:** `['tenant', 'number', 'created_at', 'updated_at', 'reviewed_at']`
- **Fields:** `['order', 'customer_party', 'user', 'transaction_amount', 'currency', 'risk_score', 'risk_tier', 'recommended_action', 'actual_decision', 'avs_result_code', 'cvv_result_code', 'ip_address', 'billing_country', 'ip_country', 'is_geo_mismatch', 'is_proxy_or_vpn', 'device_fingerprint', 'velocity_count_24h', 'risk_factors_summary', 'analyst_user', 'analyst_notes']`

### 2.3 `ChargebackDisputeForm` (`apps/ecommerce/forms/FraudRisk/ChargebackDisputes.py`)
- **Model:** `ChargebackDispute`
- **Exclude:** `['tenant', 'number', 'created_at', 'updated_at', 'representment_submitted_at', 'resolved_at']`
- **Fields:** `['order', 'customer_party', 'currency', 'dispute_amount', 'dispute_fee', 'gateway_dispute_id', 'payment_method_type', 'card_brand', 'reason_category', 'reason_code', 'stage', 'evidence_due_date', 'evidence_summary', 'representment_notes', 'outcome_notes']`

### 2.4 `AccountSecurityAlertForm` (`apps/ecommerce/forms/FraudRisk/AccountSecurityAlerts.py`)
- **Model:** `AccountSecurityAlert`
- **Exclude:** `['tenant', 'number', 'created_at', 'updated_at', 'resolved_at']`
- **Fields:** `['user', 'party', 'alert_type', 'severity', 'status', 'automated_action_taken', 'ip_address', 'location_info', 'user_agent', 'incident_details', 'assigned_investigator', 'investigation_notes', 'resolved_by']`

---

## 3. URLs & View Names Contract

All routes defined under `apps/ecommerce/urls/FraudRisk/` with prefix `/ecommerce/fraud-risk/`:

| View Function | URL Name | Route |
|---|---|---|
| `fraud_risk_hub` | `ecommerce:fraud_risk_hub` | `fraud-risk/` |
| `fraud_rule_list` | `ecommerce:fraud_rule_list` | `fraud-risk/rules/` |
| `fraud_rule_create` | `ecommerce:fraud_rule_create` | `fraud-risk/rules/create/` |
| `fraud_rule_detail` | `ecommerce:fraud_rule_detail` | `fraud-risk/rules/<int:pk>/` |
| `fraud_rule_edit` | `ecommerce:fraud_rule_edit` | `fraud-risk/rules/<int:pk>/edit/` |
| `fraud_rule_delete` | `ecommerce:fraud_rule_delete` | `fraud-risk/rules/<int:pk>/delete/` |
| `transaction_risk_assessment_list` | `ecommerce:transaction_risk_assessment_list` | `fraud-risk/assessments/` |
| `transaction_risk_assessment_create` | `ecommerce:transaction_risk_assessment_create` | `fraud-risk/assessments/create/` |
| `transaction_risk_assessment_detail` | `ecommerce:transaction_risk_assessment_detail` | `fraud-risk/assessments/<int:pk>/` |
| `transaction_risk_assessment_edit` | `ecommerce:transaction_risk_assessment_edit` | `fraud-risk/assessments/<int:pk>/edit/` |
| `transaction_risk_assessment_delete` | `ecommerce:transaction_risk_assessment_delete` | `fraud-risk/assessments/<int:pk>/delete/` |
| `chargeback_dispute_list` | `ecommerce:chargeback_dispute_list` | `fraud-risk/disputes/` |
| `chargeback_dispute_create` | `ecommerce:chargeback_dispute_create` | `fraud-risk/disputes/create/` |
| `chargeback_dispute_detail` | `ecommerce:chargeback_dispute_detail` | `fraud-risk/disputes/<int:pk>/` |
| `chargeback_dispute_edit` | `ecommerce:chargeback_dispute_edit` | `fraud-risk/disputes/<int:pk>/edit/` |
| `chargeback_dispute_delete` | `ecommerce:chargeback_dispute_delete` | `fraud-risk/disputes/<int:pk>/delete/` |
| `account_security_alert_list` | `ecommerce:account_security_alert_list` | `fraud-risk/alerts/` |
| `account_security_alert_create` | `ecommerce:account_security_alert_create` | `fraud-risk/alerts/create/` |
| `account_security_alert_detail` | `ecommerce:account_security_alert_detail` | `fraud-risk/alerts/<int:pk>/` |
| `account_security_alert_edit` | `ecommerce:account_security_alert_edit` | `fraud-risk/alerts/<int:pk>/edit/` |
| `account_security_alert_delete` | `ecommerce:account_security_alert_delete` | `fraud-risk/alerts/<int:pk>/delete/` |

---

## 4. Views & Context Keys Contract

Every view context key pinned to prevent silent blank regions or template rendering defects:

### 4.1 Hub View (`fraud_risk_hub`)
- **Template:** `ecommerce/fraud_risk/fraud_risk_hub.html`
- **Context Keys:**
  - `total_rules`: integer
  - `active_rules`: integer
  - `total_assessments`: integer
  - `high_risk_assessments`: integer
  - `pending_reviews`: integer
  - `total_disputes`: integer
  - `open_disputes`: integer
  - `dispute_amount_total`: Decimal
  - `total_alerts`: integer
  - `open_alerts`: integer
  - `critical_alerts`: integer
  - `recent_assessments`: queryset of `TransactionRiskAssessment`
  - `recent_disputes`: queryset of `ChargebackDispute`
  - `recent_alerts`: queryset of `AccountSecurityAlert`

### 4.2 `FraudRule` Views
- **List View Context (`fraud_rule_list`):**
  - `rules`: page object list
  - `page_obj`: Django Paginator page
  - `paginator`: Django Paginator instance
  - `is_paginated`: boolean
  - `total_count`: integer
  - `search_query`: `request.GET.get('q', '')`
  - `scope_filter`: `request.GET.get('scope', '')`
  - `type_filter`: `request.GET.get('type', '')`
  - `action_filter`: `request.GET.get('action', '')`
  - `is_active_filter`: `request.GET.get('is_active', '')`
  - `scope_choices`: `FraudRule.RULE_SCOPE_CHOICES`
  - `type_choices`: `FraudRule.RULE_TYPE_CHOICES`
  - `action_choices`: `FraudRule.ACTION_CHOICES`
- **Detail View Context (`fraud_rule_detail`):**
  - `rule`: `FraudRule` instance
- **Form View Context (`fraud_rule_create` / `fraud_rule_edit`):**
  - `form`: `FraudRuleForm`
  - `rule`: `FraudRule` instance (in edit mode)
  - `is_edit`: boolean

### 4.3 `TransactionRiskAssessment` Views
- **List View Context (`transaction_risk_assessment_list`):**
  - `assessments`: page object list
  - `page_obj`: Django Paginator page
  - `paginator`: Django Paginator instance
  - `is_paginated`: boolean
  - `total_count`: integer
  - `search_query`: `request.GET.get('q', '')`
  - `tier_filter`: `request.GET.get('tier', '')`
  - `action_filter`: `request.GET.get('action', '')`
  - `decision_filter`: `request.GET.get('decision', '')`
  - `tier_choices`: `TransactionRiskAssessment.RISK_TIER_CHOICES`
  - `action_choices`: `TransactionRiskAssessment.RECOMMENDED_ACTION_CHOICES`
  - `decision_choices`: `TransactionRiskAssessment.ACTUAL_DECISION_CHOICES`
- **Detail View Context (`transaction_risk_assessment_detail`):**
  - `assessment`: `TransactionRiskAssessment` instance
- **Form View Context (`transaction_risk_assessment_create` / `transaction_risk_assessment_edit`):**
  - `form`: `TransactionRiskAssessmentForm`
  - `assessment`: `TransactionRiskAssessment` instance (in edit mode)
  - `is_edit`: boolean

### 4.4 `ChargebackDispute` Views
- **List View Context (`chargeback_dispute_list`):**
  - `disputes`: page object list
  - `page_obj`: Django Paginator page
  - `paginator`: Django Paginator instance
  - `is_paginated`: boolean
  - `total_count`: integer
  - `search_query`: `request.GET.get('q', '')`
  - `stage_filter`: `request.GET.get('stage', '')`
  - `reason_filter`: `request.GET.get('reason', '')`
  - `stage_choices`: `ChargebackDispute.STAGE_CHOICES`
  - `reason_choices`: `ChargebackDispute.REASON_CATEGORY_CHOICES`
- **Detail View Context (`chargeback_dispute_detail`):**
  - `dispute`: `ChargebackDispute` instance
- **Form View Context (`chargeback_dispute_create` / `chargeback_dispute_edit`):**
  - `form`: `ChargebackDisputeForm`
  - `dispute`: `ChargebackDispute` instance (in edit mode)
  - `is_edit`: boolean

### 4.5 `AccountSecurityAlert` Views
- **List View Context (`account_security_alert_list`):**
  - `alerts`: page object list
  - `page_obj`: Django Paginator page
  - `paginator`: Django Paginator instance
  - `is_paginated`: boolean
  - `total_count`: integer
  - `search_query`: `request.GET.get('q', '')`
  - `type_filter`: `request.GET.get('type', '')`
  - `severity_filter`: `request.GET.get('severity', '')`
  - `status_filter`: `request.GET.get('status', '')`
  - `type_choices`: `AccountSecurityAlert.ALERT_TYPE_CHOICES`
  - `severity_choices`: `AccountSecurityAlert.SEVERITY_CHOICES`
  - `status_choices`: `AccountSecurityAlert.STATUS_CHOICES`
- **Detail View Context (`account_security_alert_detail`):**
  - `alert`: `AccountSecurityAlert` instance
- **Form View Context (`account_security_alert_create` / `account_security_alert_edit`):**
  - `form`: `AccountSecurityAlertForm`
  - `alert`: `AccountSecurityAlert` instance (in edit mode)
  - `is_edit`: boolean

---

## 5. Templates & Design System Contract

- Base template: `base.html`
- Color-named badges ONLY (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`). NO semantic `-success` or `-danger` variants.
- Stat card color styles: `blue`, `green`, `orange`, `purple`, `slate` only.
- Lucide icons: `shield`, `alert-triangle`, `shield-alert`, `credit-card`, `activity`, `check-circle`, `x-circle`, `eye`, `pencil`, `trash-2`.

---

## 6. Seeder Contract (`apps/ecommerce/management/commands/seed_ecommerce.py`)

- Adds 9.18 demo data for both `acme` and `globex` tenants:
  - 4 `FraudRule` records (velocity check, amount threshold, proxy detection, whitelist).
  - 3 `TransactionRiskAssessment` records (1 low risk auto-approved, 1 medium risk analyst review, 1 high risk auto-declined).
  - 2 `ChargebackDispute` records (1 needs response with pending evidence deadline, 1 won with completed representment).
  - 3 `AccountSecurityAlert` records (1 suspicious login, 1 brute force credential stuffing, 1 AML velocity alert).
- Idempotent: checks `FraudRule.objects.filter(tenant=tenant).exists()` and uses `get_or_create`.

---

## 7. Navigation & Live Links Contract (`apps/core/navigation.py`)

Add to `LIVE_LINKS["9.18"]`:
```python
LIVE_LINKS["9.18"] = {
    "Transaction Fraud Detection": "ecommerce:fraud_rule_list",
    "Machine Learning Risk Scoring": "ecommerce:transaction_risk_assessment_list",
    "Chargeback Management": "ecommerce:chargeback_dispute_list",
    "Account Takeover Prevention": "ecommerce:account_security_alert_list",
    "Compliance Screening": "ecommerce:fraud_risk_hub",
}
```
