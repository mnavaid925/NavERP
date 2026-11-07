# Contract — Sub-module 10.16: Alerts, Subscriptions & Distribution (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.16 Alerts, Subscriptions & Distribution • **Module:** 10 Business Intelligence • **App:** `apps/bi`
- **Date:** 2026-11-07 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (extended across 10.1 through 10.15). Incremental migration: `0036_...` (previous leaf: `0035_searchdiscoveryindex_idx_bsdi_ten_feat_rw.py`).
- **Package Layout:** `AlertsSubscriptions/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/alerts_subscriptions/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `BiAlertRule` (`apps/bi/models/AlertsSubscriptions/BiAlertRules.py`)
- **Table:** `bi_alert_rule`
- **Number Prefix:** `BALR` (`BALR-00001`)
- **CHOICES:**
  - `ALERT_TYPE_CHOICES = [('kpi_threshold', 'KPI Metric Threshold'), ('anomaly_detection', 'Statistical Anomaly Trigger'), ('query_threshold', 'Ad-Hoc Query Result Count'), ('trend_variance', 'Trend & Percentage Variance')]`
  - `CONDITION_OPERATOR_CHOICES = [('gt', 'Greater Than (>)'), ('gte', 'Greater Than or Equal (>=)'), ('lt', 'Less Than (<)'), ('lte', 'Less Than or Equal (<=)'), ('eq', 'Equals (==)'), ('outside_range', 'Outside Target Range'), ('pct_change_gt', 'Percentage Increase Exceeds (%)'), ('pct_change_lt', 'Percentage Drop Exceeds (%)'), ('anomaly_flagged', 'Anomaly Outlier Flagged')]`
  - `SEVERITY_CHOICES = [('info', 'Informational'), ('warning', 'Warning'), ('critical', 'Critical / Urgent')]`
  - `EVALUATION_CADENCE_CHOICES = [('on_data_refresh', 'On Ingestion / Pipeline Refresh'), ('every_15_mins', 'Every 15 Minutes'), ('hourly', 'Hourly'), ('daily', 'Daily'), ('weekly', 'Weekly')]`
  - `TRIGGER_FREQUENCY_CHOICES = [('every_time', 'Send Notification Every Time Breach Occurs'), ('once_until_resolved', 'Send Once Until Condition Clears'), ('one_off', 'Single Disposable Trigger Then Disable')]`
  - `DELIVERY_CHANNEL_CHOICES = [('in_app_only', 'In-App Notification Center Only'), ('in_app_email', 'In-App and Email Digest'), ('slack_webhook', 'Slack / Microsoft Teams Webhook'), ('multi_channel', 'All Channels (In-App, Email, Webhook)')]`
  - `DOWNSTREAM_WORKFLOW_CHOICES = [('none', 'No Automated Workflow'), ('create_task', 'Create Follow-Up Project Task'), ('request_approval', 'Submit Incident Approval Request'), ('trigger_webhook', 'Dispatch Downstream Automation Webhook')]`
  - `STATUS_CHOICES = [('active', 'Active & Monitoring'), ('paused', 'Paused / Inactive'), ('tripped', 'Tripped / In Breach State'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `description`: `TextField(blank=True)`
  - `alert_type`: `CharField(max_length=24, choices=ALERT_TYPE_CHOICES, default='kpi_threshold')`
  - `kpi_definition`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='alert_rules')`
  - `anomaly_detection`: `ForeignKey('bi.StatisticalAnomaly', null=True, blank=True, on_delete=models.SET_NULL, related_name='alert_rules')`
  - `condition_operator`: `CharField(max_length=24, choices=CONDITION_OPERATOR_CHOICES, default='gt')`
  - `threshold_value`: `DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))`
  - `secondary_threshold_value`: `DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)`
  - `severity`: `CharField(max_length=16, choices=SEVERITY_CHOICES, default='warning')`
  - `evaluation_cadence`: `CharField(max_length=20, choices=EVALUATION_CADENCE_CHOICES, default='hourly')`
  - `trigger_frequency`: `CharField(max_length=24, choices=TRIGGER_FREQUENCY_CHOICES, default='once_until_resolved')`
  - `delivery_channel`: `CharField(max_length=20, choices=DELIVERY_CHANNEL_CHOICES, default='in_app_email')`
  - `recipient_users`: `ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='bi_alert_subscriptions')`
  - `notification_email_list`: `TextField(blank=True, help_text="Comma-separated external subscriber email addresses")`
  - `webhook_url`: `URLField(blank=True, help_text="Slack/Teams or external automation webhook endpoint")`
  - `downstream_workflow`: `CharField(max_length=24, choices=DOWNSTREAM_WORKFLOW_CHOICES, default='none')`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='active')`
  - `last_evaluated_at`: `DateTimeField(null=True, blank=True)`
  - `last_triggered_at`: `DateTimeField(null=True, blank=True)`
  - `trigger_count`: `PositiveIntegerField(default=0)`
  - `last_trigger_value`: `DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_bi_alerts')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_balr_tenant_num_uniq')`
  - `Index(fields=['tenant', 'alert_type'], name='idx_balr_ten_type')`
  - `Index(fields=['tenant', 'status'], name='idx_balr_ten_status')`
  - `Index(fields=['tenant', 'severity'], name='idx_balr_ten_sev')`
  - `Index(fields=['tenant', 'last_evaluated_at'], name='idx_balr_ten_eval')`

---

### 1.2 `ReportSubscription` (`apps/bi/models/AlertsSubscriptions/ReportSubscriptions.py`)
- **Table:** `bi_report_subscription`
- **Number Prefix:** `BSUB` (`BSUB-00001`)
- **CHOICES:**
  - `TARGET_ASSET_TYPE_CHOICES = [('dashboard', 'Executive Dashboard'), ('report', 'Operational Report')]`
  - `EXPORT_FORMAT_CHOICES = [('pdf', 'Portable Document Format (PDF)'), ('xlsx', 'Microsoft Excel Spreadsheet (XLSX)'), ('csv', 'Comma-Separated Values (CSV)'), ('html_inline', 'Interactive HTML Inline Digest')]`
  - `CADENCE_CHOICES = [('daily', 'Daily Morning Digest'), ('weekly', 'Weekly Monday Summary'), ('monthly', 'Monthly Financial Close Summary'), ('quarterly', 'Quarterly Review'), ('cron', 'Custom Cron Schedule')]`
  - `BURST_MODE_CHOICES = [('broadcast', 'Standard Broadcast (Identical Content to All Recipients)'), ('slice_by_user', 'Recipient-Personalized Data Bursting (Row-Level Access)'), ('slice_by_org_unit', 'Department / OrgUnit Sliced Bursting')]`
  - `STATUS_CHOICES = [('active', 'Active & Scheduled'), ('paused', 'Paused Delivery'), ('failed', 'Delivery Errored / Retrying'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `target_asset_type`: `CharField(max_length=16, choices=TARGET_ASSET_TYPE_CHOICES, default='dashboard')`
  - `dashboard`: `ForeignKey('bi.BiDashboard', null=True, blank=True, on_delete=models.SET_NULL, related_name='subscriptions')`
  - `report`: `ForeignKey('bi.ReportDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='subscriptions')`
  - `export_format`: `CharField(max_length=16, choices=EXPORT_FORMAT_CHOICES, default='pdf')`
  - `cadence`: `CharField(max_length=16, choices=CADENCE_CHOICES, default='weekly')`
  - `scheduled_time`: `TimeField(default=datetime.time(8, 0))`
  - `cron_expression`: `CharField(max_length=64, blank=True, default='0 8 * * 1')`
  - `burst_mode`: `CharField(max_length=20, choices=BURST_MODE_CHOICES, default='broadcast')`
  - `subscriber_users`: `ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='bi_report_subscriptions')`
  - `subscriber_org_units`: `ManyToManyField('core.OrgUnit', blank=True, related_name='bi_report_subscriptions')`
  - `external_recipient_emails`: `TextField(blank=True)`
  - `filter_overrides`: `JSONField(default=dict, blank=True)`
  - `include_cover_page`: `BooleanField(default=True)`
  - `skip_if_empty`: `BooleanField(default=False)`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='active')`
  - `last_run_at`: `DateTimeField(null=True, blank=True)`
  - `next_run_at`: `DateTimeField(null=True, blank=True)`
  - `run_count`: `PositiveIntegerField(default=0)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_bi_subscriptions')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bsub_tenant_num_uniq')`
  - `Index(fields=['tenant', 'target_asset_type'], name='idx_bsub_ten_target')`
  - `Index(fields=['tenant', 'cadence'], name='idx_bsub_ten_cadence')`
  - `Index(fields=['tenant', 'status'], name='idx_bsub_ten_status')`
  - `Index(fields=['tenant', 'next_run_at'], name='idx_bsub_ten_next')`

---

### 1.3 `DistributionBurstRun` (`apps/bi/models/AlertsSubscriptions/DistributionBurstRuns.py`)
- **Table:** `bi_distribution_burst_run`
- **Number Prefix:** `BBRS` (`BBRS-00001`)
- **CHOICES:**
  - `RUN_TRIGGER_CHOICES = [('scheduled_subscription', 'Scheduled Subscription Batch'), ('ad_hoc_manual', 'Manual Ad-Hoc Burst Dispatch'), ('alert_triggered', 'Triggered from Tripped Alert Rule')]`
  - `DELIVERY_CHANNEL_CHOICES = [('email', 'Email (SMTP)'), ('sftp', 'Secure FTP Drop (SFTP)'), ('portal_inbox', 'In-App Portal Inbox'), ('webhook', 'External Webhook')]`
  - `STATUS_CHOICES = [('queued', 'Queued for Generation'), ('processing', 'Processing & Slicing Batches'), ('completed', 'Completed Successfully'), ('partial_failure', 'Partial Failure (Some Recipients Failed)'), ('failed', 'Failed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `subscription`: `ForeignKey('bi.ReportSubscription', null=True, blank=True, on_delete=models.SET_NULL, related_name='burst_runs')`
  - `alert_rule`: `ForeignKey('bi.BiAlertRule', null=True, blank=True, on_delete=models.SET_NULL, related_name='burst_runs')`
  - `run_trigger`: `CharField(max_length=24, choices=RUN_TRIGGER_CHOICES, default='scheduled_subscription')`
  - `delivery_channel`: `CharField(max_length=16, choices=DELIVERY_CHANNEL_CHOICES, default='email')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='completed')`
  - `recipient_count`: `PositiveIntegerField(default=1)`
  - `delivered_count`: `PositiveIntegerField(default=1)`
  - `failed_count`: `PositiveIntegerField(default=0)`
  - `execution_duration_ms`: `IntegerField(default=0)`
  - `generated_file_name`: `CharField(max_length=255, blank=True)`
  - `file_size_bytes`: `BigIntegerField(default=0)`
  - `burst_slicing_metadata`: `JSONField(default=dict, blank=True)`
  - `error_summary`: `TextField(blank=True)`
  - `executed_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='executed_burst_runs')`
  - `started_at`: `DateTimeField(default=timezone.now)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bbrs_tenant_num_uniq')`
  - `Index(fields=['tenant', 'run_trigger'], name='idx_bbrs_ten_trig')`
  - `Index(fields=['tenant', 'status'], name='idx_bbrs_ten_stat')`
  - `Index(fields=['tenant', 'started_at'], name='idx_bbrs_ten_start')`

---

### 1.4 `BiNotificationItem` (`apps/bi/models/AlertsSubscriptions/BiNotificationItems.py`)
- **Table:** `bi_notification_item`
- **Number Prefix:** `BNTF` (`BNTF-00001`)
- **CHOICES:**
  - `SEVERITY_CHOICES = [('info', 'Informational'), ('warning', 'Warning'), ('critical', 'Critical / Urgent')]`
  - `CATEGORY_CHOICES = [('kpi_alert', 'KPI Threshold Alert'), ('anomaly_alert', 'Statistical Anomaly Alert'), ('subscription_digest', 'Report Subscription Delivery'), ('workflow_task', 'Triggered Workflow Task'), ('system_bulletin', 'System & Lineage Bulletin')]`
  - `STATUS_CHOICES = [('unread', 'Unread'), ('read', 'Read'), ('acknowledged', 'Acknowledged'), ('snoozed', 'Snoozed'), ('escalated', 'Escalated'), ('dismissed', 'Dismissed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `recipient`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bi_notifications')`
  - `title`: `CharField(max_length=200)`
  - `message`: `TextField()`
  - `severity`: `CharField(max_length=16, choices=SEVERITY_CHOICES, default='info')`
  - `category`: `CharField(max_length=24, choices=CATEGORY_CHOICES, default='kpi_alert')`
  - `status`: `CharField(max_length=16, choices=STATUS_CHOICES, default='unread')`
  - `alert_rule`: `ForeignKey('bi.BiAlertRule', null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications')`
  - `burst_run`: `ForeignKey('bi.DistributionBurstRun', null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications')`
  - `action_url`: `CharField(max_length=255, blank=True)`
  - `read_at`: `DateTimeField(null=True, blank=True)`
  - `acknowledged_at`: `DateTimeField(null=True, blank=True)`
  - `acknowledged_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')`
  - `acknowledgment_notes`: `TextField(blank=True)`
  - `snoozed_until`: `DateTimeField(null=True, blank=True)`
  - `escalation_level`: `PositiveIntegerField(default=0)`
  - `escalated_to`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='escalated_bi_notifications')`
  - `workflow_converted`: `BooleanField(default=False)`
  - `workflow_reference`: `CharField(max_length=100, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bntf_tenant_num_uniq')`
  - `Index(fields=['tenant', 'recipient', 'status'], name='idx_bntf_ten_rec_stat')`
  - `Index(fields=['tenant', 'severity'], name='idx_bntf_ten_sev')`
  - `Index(fields=['tenant', 'category'], name='idx_bntf_ten_cat')`
  - `Index(fields=['tenant', 'created_at'], name='idx_bntf_ten_created')`

---

## 2. Forms Contract

### 2.1 `BiAlertRuleForm` (`apps/bi/forms/AlertsSubscriptions/BiAlertRules.py`)
- **Meta.model:** `BiAlertRule`
- **Fields Included:** `name`, `description`, `alert_type`, `kpi_definition`, `anomaly_detection`, `condition_operator`, `threshold_value`, `secondary_threshold_value`, `severity`, `evaluation_cadence`, `trigger_frequency`, `delivery_channel`, `recipient_users`, `notification_email_list`, `webhook_url`, `downstream_workflow`, `status`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`, `created_by`, `last_evaluated_at`, `last_triggered_at`, `trigger_count`, `last_trigger_value`

### 2.2 `ReportSubscriptionForm` (`apps/bi/forms/AlertsSubscriptions/ReportSubscriptions.py`)
- **Meta.model:** `ReportSubscription`
- **Fields Included:** `name`, `target_asset_type`, `dashboard`, `report`, `export_format`, `cadence`, `scheduled_time`, `cron_expression`, `burst_mode`, `subscriber_users`, `subscriber_org_units`, `external_recipient_emails`, `filter_overrides`, `include_cover_page`, `skip_if_empty`, `status`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`, `created_by`, `last_run_at`, `next_run_at`, `run_count`

### 2.3 `DistributionBurstRunForm` (`apps/bi/forms/AlertsSubscriptions/DistributionBurstRuns.py`)
- **Meta.model:** `DistributionBurstRun`
- **Fields Included:** `subscription`, `alert_rule`, `run_trigger`, `delivery_channel`, `status`, `recipient_count`, `generated_file_name`, `file_size_bytes`, `burst_slicing_metadata`, `error_summary`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`, `executed_by`, `started_at`, `completed_at`, `execution_duration_ms`, `delivered_count`, `failed_count`

### 2.4 `BiNotificationItemForm` (`apps/bi/forms/AlertsSubscriptions/BiNotificationItems.py`)
- **Meta.model:** `BiNotificationItem`
- **Fields Included:** `recipient`, `title`, `message`, `severity`, `category`, `status`, `alert_rule`, `burst_run`, `action_url`, `acknowledgment_notes`, `snoozed_until`
- **Exclusions:** `tenant`, `number`, `created_at`, `updated_at`, `read_at`, `acknowledged_at`, `acknowledged_by`, `escalation_level`, `escalated_to`, `workflow_converted`, `workflow_reference`

---

## 3. URLs & Views Contract

Namespace: `bi:*`

### 3.1 `BiAlertRule` URLs
- `bi:bi_alert_rule_list` -> `alerts/` (`bi_alert_rule_list`)
- `bi:bi_alert_rule_create` -> `alerts/create/` (`bi_alert_rule_create`)
- `bi:bi_alert_rule_detail` -> `alerts/<int:pk>/` (`bi_alert_rule_detail`)
- `bi:bi_alert_rule_edit` -> `alerts/<int:pk>/edit/` (`bi_alert_rule_edit`)
- `bi:bi_alert_rule_delete` -> `alerts/<int:pk>/delete/` (`bi_alert_rule_delete`)
- `bi:bi_alert_rule_test_evaluate` -> `alerts/<int:pk>/evaluate/` (`bi_alert_rule_test_evaluate`)

### 3.2 `ReportSubscription` URLs
- `bi:report_subscription_list` -> `subscriptions/` (`report_subscription_list`)
- `bi:report_subscription_create` -> `subscriptions/create/` (`report_subscription_create`)
- `bi:report_subscription_detail` -> `subscriptions/<int:pk>/` (`report_subscription_detail`)
- `bi:report_subscription_edit` -> `subscriptions/<int:pk>/edit/` (`report_subscription_edit`)
- `bi:report_subscription_delete` -> `subscriptions/<int:pk>/delete/` (`report_subscription_delete`)
- `bi:report_subscription_run_now` -> `subscriptions/<int:pk>/run-now/` (`report_subscription_run_now`)

### 3.3 `DistributionBurstRun` URLs
- `bi:distribution_burst_run_list` -> `burst-runs/` (`distribution_burst_run_list`)
- `bi:distribution_burst_run_create` -> `burst-runs/create/` (`distribution_burst_run_create`)
- `bi:distribution_burst_run_detail` -> `burst-runs/<int:pk>/` (`distribution_burst_run_detail`)
- `bi:distribution_burst_run_edit` -> `burst-runs/<int:pk>/edit/` (`distribution_burst_run_edit`)
- `bi:distribution_burst_run_delete` -> `burst-runs/<int:pk>/delete/` (`distribution_burst_run_delete`)

### 3.4 `BiNotificationItem` URLs
- `bi:bi_notification_item_list` -> `notifications/` (`bi_notification_item_list`)
- `bi:bi_notification_item_create` -> `notifications/create/` (`bi_notification_item_create`)
- `bi:bi_notification_item_detail` -> `notifications/<int:pk>/` (`bi_notification_item_detail`)
- `bi:bi_notification_item_edit` -> `notifications/<int:pk>/edit/` (`bi_notification_item_edit`)
- `bi:bi_notification_item_delete` -> `notifications/<int:pk>/delete/` (`bi_notification_item_delete`)
- `bi:notification_center` -> `notification-center/` (`notification_center`)
- `bi:notification_mark_read` -> `notifications/<int:pk>/mark-read/` (`notification_mark_read`)
- `bi:notification_acknowledge` -> `notifications/<int:pk>/acknowledge/` (`notification_acknowledge`)
- `bi:notification_snooze` -> `notifications/<int:pk>/snooze/` (`notification_snooze`)
- `bi:notification_escalate` -> `notifications/<int:pk>/escalate/` (`notification_escalate`)

---

## 4. View Context Keys Contract (Pinned Variable Names)

### 4.1 `BiAlertRule` Views
- **List view (`bi:bi_alert_rule_list`):**
  - List variable: `rules` (paginated `Page` object)
  - Choices: `alert_type_choices`, `severity_choices`, `status_choices`
  - Counts/KPIs: `total_count`, `active_count`, `tripped_count`, `critical_count`
  - Filter state: `q`, `selected_alert_type`, `selected_severity`, `selected_status`
- **Detail view (`bi:bi_alert_rule_detail`):**
  - Object variable: `rule`
  - Child collections: `recent_notifications`, `recent_burst_runs`
- **Form view (`bi_alert_rule_create` / `bi_alert_rule_edit`):**
  - Form: `form`
  - Object variable (edit mode): `rule`
  - FK querysets: `kpi_definitions`, `anomalies`, `users`

### 4.2 `ReportSubscription` Views
- **List view (`bi:report_subscription_list`):**
  - List variable: `subscriptions` (paginated `Page` object)
  - Choices: `target_asset_type_choices`, `cadence_choices`, `export_format_choices`, `status_choices`
  - Counts/KPIs: `total_count`, `active_count`, `pdf_count`, `excel_count`
  - Filter state: `q`, `selected_target_type`, `selected_cadence`, `selected_format`, `selected_status`
- **Detail view (`bi:report_subscription_detail`):**
  - Object variable: `subscription`
  - Child collections: `recent_burst_runs`
- **Form view (`report_subscription_create` / `report_subscription_edit`):**
  - Form: `form`
  - Object variable (edit mode): `subscription`
  - FK querysets: `dashboards`, `reports`, `users`, `org_units`

### 4.3 `DistributionBurstRun` Views
- **List view (`bi:distribution_burst_run_list`):**
  - List variable: `burst_runs` (paginated `Page` object)
  - Choices: `run_trigger_choices`, `delivery_channel_choices`, `status_choices`
  - Counts/KPIs: `total_runs`, `completed_runs`, `failed_runs`, `total_delivered_recipients`
  - Filter state: `q`, `selected_trigger`, `selected_channel`, `selected_status`
- **Detail view (`bi:distribution_burst_run_detail`):**
  - Object variable: `burst_run`
  - Child collections: `notifications`
- **Form view (`distribution_burst_run_create` / `distribution_burst_run_edit`):**
  - Form: `form`
  - Object variable (edit mode): `burst_run`
  - FK querysets: `subscriptions`, `rules`

### 4.4 `BiNotificationItem` Views & Notification Center
- **List view (`bi:bi_notification_item_list`):**
  - List variable: `notifications` (paginated `Page` object)
  - Choices: `severity_choices`, `category_choices`, `status_choices`
  - Counts/KPIs: `total_count`, `unread_count`, `critical_count`, `escalated_count`
  - Filter state: `q`, `selected_severity`, `selected_category`, `selected_status`
- **Notification Center workspace (`bi:notification_center`):**
  - Primary list: `inbox_items` (user's active notifications)
  - Counts: `unread_count`, `acknowledged_count`, `snoozed_count`, `escalated_count`
  - Choices: `severity_choices`, `category_choices`
  - Filter state: `active_tab` (`all`, `unread`, `critical`, `snoozed`, `escalated`), `selected_category`
- **Detail view (`bi:bi_notification_item_detail`):**
  - Object variable: `notification`
- **Form view (`bi_notification_item_create` / `bi_notification_item_edit`):**
  - Form: `form`
  - Object variable (edit mode): `notification`
  - FK querysets: `users`, `rules`, `burst_runs`

---

## 5. Navigation Contract (`apps/core/navigation.py`)

`LIVE_LINKS["10.16"]` mapping:
```python
"10.16": {
    "Threshold & Anomaly Alerts": "bi:bi_alert_rule_list",
    "Report Subscriptions": "bi:report_subscription_list",
    "Distribution & Bursting": "bi:distribution_burst_run_list",
    "Notification Center": "bi:bi_notification_item_list",
    "Trigger-Based Workflows": "bi:bi_alert_rule_list",
    # Plural and workspace aliases
    "Alert Rules": "bi:bi_alert_rule_list",
    "Report & Dashboard Subscriptions": "bi:report_subscription_list",
    "Distribution Burst Runs": "bi:distribution_burst_run_list",
    "Notification Items": "bi:bi_notification_item_list",
    "Notification Inbox": "bi:notification_center",
    "Notification Workspace": "bi:notification_center",
},
```
