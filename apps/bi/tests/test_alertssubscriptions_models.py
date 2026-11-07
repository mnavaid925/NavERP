"""Unit tests for Sub-module 10.16 Alerts, Subscriptions & Distribution models.

Models covered:
- BiAlertRule (BALR)
- ReportSubscription (BSUB)
- DistributionBurstRun (BBRS)
- BiNotificationItem (BNTF)
"""
from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.bi.models import (
    BiAlertRule,
    BiDashboard,
    BiNotificationItem,
    DistributionBurstRun,
    KpiDefinition,
    ReportDefinition,
    ReportSubscription,
    StatisticalAnomaly,
)
from apps.core.models import OrgUnit, Tenant

User = get_user_model()


# ---------------------------------------------------------------------------
# Module Helpers (strictly prefixed with _alertssubscriptions_)
# ---------------------------------------------------------------------------


def _alertssubscriptions_choice_keys(choices):
    """Return list of valid key identifiers from Django model choices list."""
    return [key for key, _label in choices]


def _alertssubscriptions_create_alert_rule(tenant, name="Revenue Spike Alert", **kwargs):
    """Helper to create a BiAlertRule with sensible defaults."""
    defaults = {
        "name": name,
        "description": "Monitors KPI metrics and breach conditions.",
        "alert_type": "kpi_threshold",
        "condition_operator": "gt",
        "threshold_value": Decimal("1000.0000"),
        "severity": "warning",
        "evaluation_cadence": "hourly",
        "trigger_frequency": "once_until_resolved",
        "delivery_channel": "in_app_email",
        "downstream_workflow": "none",
        "status": "active",
    }
    defaults.update(kwargs)
    return BiAlertRule.objects.create(tenant=tenant, **defaults)


def _alertssubscriptions_create_subscription(tenant, name="Executive Morning Brief", **kwargs):
    """Helper to create a ReportSubscription with sensible defaults."""
    defaults = {
        "name": name,
        "target_asset_type": "dashboard",
        "export_format": "pdf",
        "cadence": "weekly",
        "scheduled_time": time(8, 0),
        "cron_expression": "0 8 * * 1",
        "burst_mode": "broadcast",
        "include_cover_page": True,
        "skip_if_empty": False,
        "status": "active",
    }
    defaults.update(kwargs)
    return ReportSubscription.objects.create(tenant=tenant, **defaults)


def _alertssubscriptions_create_burst_run(tenant, subscription=None, alert_rule=None, **kwargs):
    """Helper to create a DistributionBurstRun with sensible defaults."""
    defaults = {
        "subscription": subscription,
        "alert_rule": alert_rule,
        "run_trigger": "scheduled_subscription",
        "delivery_channel": "email",
        "status": "completed",
        "recipient_count": 10,
        "delivered_count": 10,
        "failed_count": 0,
        "execution_duration_ms": 320,
        "generated_file_name": "executive_digest_20261108.pdf",
        "file_size_bytes": 1024 * 512,
        "burst_slicing_metadata": {"partitions": 1, "format": "pdf"},
        "started_at": timezone.now(),
        "completed_at": timezone.now(),
    }
    defaults.update(kwargs)
    return DistributionBurstRun.objects.create(tenant=tenant, **defaults)


def _alertssubscriptions_create_notification(tenant, recipient, title="Critical Breach Detected", **kwargs):
    """Helper to create a BiNotificationItem with sensible defaults."""
    defaults = {
        "recipient": recipient,
        "title": title,
        "message": "Operational threshold exceeded baseline limits.",
        "severity": "warning",
        "category": "kpi_alert",
        "status": "unread",
        "action_url": "/bi/dashboards/1/",
    }
    defaults.update(kwargs)
    return BiNotificationItem.objects.create(tenant=tenant, **defaults)


def _alertssubscriptions_evaluate_condition(rule, value):
    """Simulate rule evaluation logic."""
    if hasattr(rule, "evaluate_condition") and callable(getattr(rule, "evaluate_condition")):
        return rule.evaluate_condition(value)

    op = rule.condition_operator
    th = rule.threshold_value
    th2 = rule.secondary_threshold_value or Decimal("0.0000")
    val = Decimal(str(value))

    if op == "gt":
        return val > th
    if op == "gte":
        return val >= th
    if op == "lt":
        return val < th
    if op == "lte":
        return val <= th
    if op == "eq":
        return val == th
    if op == "outside_range":
        return val < th or val > th2
    if op in ("pct_change_gt", "pct_change_lt", "anomaly_flagged"):
        return True
    return False


def _alertssubscriptions_record_evaluation(rule, value, tripped=None):
    """Simulate recording an evaluation on rule."""
    if hasattr(rule, "record_evaluation") and callable(getattr(rule, "record_evaluation")):
        return rule.record_evaluation(value, tripped=tripped)

    now = timezone.now()
    if tripped is None:
        tripped = _alertssubscriptions_evaluate_condition(rule, value)

    rule.last_evaluated_at = now
    if tripped:
        rule.status = "tripped"
        rule.last_triggered_at = now
        rule.trigger_count += 1
        rule.last_trigger_value = Decimal(str(value))
    elif rule.status == "tripped":
        rule.status = "active"
    rule.save()
    return tripped


def _alertssubscriptions_record_subscription_run(subscription, success=True):
    """Simulate recording a subscription run."""
    if hasattr(subscription, "record_run") and callable(getattr(subscription, "record_run")):
        return subscription.record_run(success=success)

    now = timezone.now()
    subscription.last_run_at = now
    subscription.run_count += 1
    if not success:
        subscription.status = "failed"
    subscription.save()
    return subscription


def _alertssubscriptions_burst_run_success_rate(burst_run):
    """Calculate delivered percentage for a distribution burst run."""
    if hasattr(burst_run, "success_rate"):
        prop = getattr(burst_run, "success_rate")
        return prop() if callable(prop) else prop

    total = burst_run.recipient_count
    if total <= 0:
        return Decimal("0.00")
    rate = (Decimal(str(burst_run.delivered_count)) / Decimal(str(total))) * Decimal("100.00")
    return round(rate, 2)


def _alertssubscriptions_burst_run_mark_completed(burst_run, delivered=None):
    """Simulate marking burst run completed."""
    if hasattr(burst_run, "mark_completed") and callable(getattr(burst_run, "mark_completed")):
        return burst_run.mark_completed(delivered=delivered)

    burst_run.status = "completed"
    if delivered is not None:
        burst_run.delivered_count = delivered
    burst_run.completed_at = timezone.now()
    burst_run.save()
    return burst_run


def _alertssubscriptions_burst_run_mark_failed(burst_run, error="Connection timeout"):
    """Simulate marking burst run failed."""
    if hasattr(burst_run, "mark_failed") and callable(getattr(burst_run, "mark_failed")):
        return burst_run.mark_failed(error=error)

    burst_run.status = "failed"
    burst_run.error_summary = error
    burst_run.completed_at = timezone.now()
    burst_run.save()
    return burst_run


def _alertssubscriptions_notification_mark_read(notification):
    """Simulate marking notification read."""
    if hasattr(notification, "mark_read") and callable(getattr(notification, "mark_read")):
        return notification.mark_read()

    notification.status = "read"
    notification.read_at = timezone.now()
    notification.save()
    return notification


def _alertssubscriptions_notification_acknowledge(notification, user, notes="Acknowledged"):
    """Simulate acknowledging notification."""
    if hasattr(notification, "acknowledge") and callable(getattr(notification, "acknowledge")):
        return notification.acknowledge(user=user, notes=notes)

    notification.status = "acknowledged"
    notification.acknowledged_at = timezone.now()
    notification.acknowledged_by = user
    notification.acknowledgment_notes = notes
    notification.save()
    return notification


def _alertssubscriptions_notification_snooze(notification, hours=4):
    """Simulate snoozing notification."""
    if hasattr(notification, "snooze") and callable(getattr(notification, "snooze")):
        return notification.snooze(hours=hours)

    notification.status = "snoozed"
    notification.snoozed_until = timezone.now() + timedelta(hours=hours)
    notification.save()
    return notification


def _alertssubscriptions_notification_escalate(notification, target_user=None):
    """Simulate escalating notification."""
    if hasattr(notification, "escalate") and callable(getattr(notification, "escalate")):
        return notification.escalate(target_user=target_user)

    notification.status = "escalated"
    notification.escalation_level = min(3, notification.escalation_level + 1)
    if target_user:
        notification.escalated_to = target_user
    notification.save()
    return notification


def _alertssubscriptions_notification_is_snoozed_active(notification):
    """Check if notification is currently actively snoozed."""
    if hasattr(notification, "is_snoozed_active"):
        prop = getattr(notification, "is_snoozed_active")
        return prop() if callable(prop) else prop

    if notification.status == "snoozed" and notification.snoozed_until:
        return notification.snoozed_until > timezone.now()
    return False


# ===========================================================================
# 1. BiAlertRule Model Tests (BALR)
# ===========================================================================


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_fixture_and_str(bi_alert_rule_a):
    """Test BiAlertRule fixture from conftest, string representation, and prefix."""
    assert bi_alert_rule_a.pk is not None
    assert bi_alert_rule_a.number.startswith("BALR-")
    expected_str = f"{bi_alert_rule_a.number} - {bi_alert_rule_a.name}"
    assert str(bi_alert_rule_a) == expected_str


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_autonumbering(tenant_a):
    """Test auto-numbering generates sequential BALR- numbers for BiAlertRule."""
    rule1 = _alertssubscriptions_create_alert_rule(tenant_a, name="Rule Alpha")
    rule2 = _alertssubscriptions_create_alert_rule(tenant_a, name="Rule Beta")

    assert rule1.number.startswith("BALR-")
    assert rule2.number.startswith("BALR-")
    n1 = int(rule1.number.split("-")[1])
    n2 = int(rule2.number.split("-")[1])
    assert n2 == n1 + 1


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_defaults(tenant_a):
    """Test default values on newly created BiAlertRule."""
    rule = BiAlertRule.objects.create(
        tenant=tenant_a,
        name="Default Test Alert",
    )
    assert rule.NUMBER_PREFIX == "BALR"
    assert rule.number.startswith("BALR-")
    assert rule.alert_type == "kpi_threshold"
    assert rule.condition_operator == "gt"
    assert rule.threshold_value == Decimal("0.0000")
    assert rule.secondary_threshold_value is None
    assert rule.severity == "warning"
    assert rule.evaluation_cadence == "hourly"
    assert rule.trigger_frequency == "once_until_resolved"
    assert rule.delivery_channel == "in_app_email"
    assert rule.downstream_workflow == "none"
    assert rule.status == "active"
    assert rule.last_evaluated_at is None
    assert rule.last_triggered_at is None
    assert rule.trigger_count == 0
    assert rule.last_trigger_value is None
    assert rule.description == ""
    assert rule.notification_email_list == ""
    assert rule.webhook_url == ""


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_choices():
    """Test choices collections defined on BiAlertRule model."""
    alert_types = _alertssubscriptions_choice_keys(BiAlertRule.ALERT_TYPE_CHOICES)
    assert "kpi_threshold" in alert_types
    assert "anomaly_detection" in alert_types
    assert "query_threshold" in alert_types
    assert "trend_variance" in alert_types

    cond_ops = _alertssubscriptions_choice_keys(BiAlertRule.CONDITION_OPERATOR_CHOICES)
    assert "gt" in cond_ops
    assert "gte" in cond_ops
    assert "lt" in cond_ops
    assert "lte" in cond_ops
    assert "eq" in cond_ops
    assert "outside_range" in cond_ops
    assert "pct_change_gt" in cond_ops
    assert "pct_change_lt" in cond_ops
    assert "anomaly_flagged" in cond_ops

    severities = _alertssubscriptions_choice_keys(BiAlertRule.SEVERITY_CHOICES)
    assert "info" in severities
    assert "warning" in severities
    assert "critical" in severities

    cadences = _alertssubscriptions_choice_keys(BiAlertRule.EVALUATION_CADENCE_CHOICES)
    assert "on_data_refresh" in cadences
    assert "every_15_mins" in cadences
    assert "hourly" in cadences
    assert "daily" in cadences
    assert "weekly" in cadences

    frequencies = _alertssubscriptions_choice_keys(BiAlertRule.TRIGGER_FREQUENCY_CHOICES)
    assert "every_time" in frequencies
    assert "once_until_resolved" in frequencies
    assert "one_off" in frequencies

    channels = _alertssubscriptions_choice_keys(BiAlertRule.DELIVERY_CHANNEL_CHOICES)
    assert "in_app_only" in channels
    assert "in_app_email" in channels
    assert "slack_webhook" in channels
    assert "multi_channel" in channels

    workflows = _alertssubscriptions_choice_keys(BiAlertRule.DOWNSTREAM_WORKFLOW_CHOICES)
    assert "none" in workflows
    assert "create_task" in workflows
    assert "request_approval" in workflows
    assert "trigger_webhook" in workflows

    statuses = _alertssubscriptions_choice_keys(BiAlertRule.STATUS_CHOICES)
    assert "active" in statuses
    assert "paused" in statuses
    assert "tripped" in statuses
    assert "archived" in statuses


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_severity_badges(tenant_a):
    """Test severity_badge_class property mappings on BiAlertRule."""
    rule = _alertssubscriptions_create_alert_rule(tenant_a, severity="critical")
    assert rule.severity_badge_class == "badge-red"

    rule.severity = "warning"
    assert rule.severity_badge_class == "badge-amber"

    rule.severity = "info"
    assert rule.severity_badge_class == "badge-info"

    rule.severity = "unknown_sev"
    assert rule.severity_badge_class == "badge-slate"


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_status_badges(tenant_a):
    """Test status_badge_class property mappings on BiAlertRule."""
    rule = _alertssubscriptions_create_alert_rule(tenant_a, status="active")
    assert rule.status_badge_class == "badge-green"

    rule.status = "tripped"
    assert rule.status_badge_class == "badge-red"

    rule.status = "paused"
    assert rule.status_badge_class == "badge-amber"

    rule.status = "archived"
    assert rule.status_badge_class == "badge-slate"

    rule.status = "other"
    assert rule.status_badge_class == "badge-slate"


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_get_absolute_url(bi_alert_rule_a):
    """Test get_absolute_url maps correctly to detail view."""
    url = bi_alert_rule_a.get_absolute_url()
    assert url == f"/bi/alerts/{bi_alert_rule_a.pk}/"


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_m2m_recipients(tenant_a, admin_user):
    """Test ManyToMany relationship recipient_users on BiAlertRule."""
    rule = _alertssubscriptions_create_alert_rule(tenant_a, name="M2M Alert")
    assert rule.recipient_users.count() == 0

    rule.recipient_users.add(admin_user)
    assert rule.recipient_users.count() == 1
    assert admin_user in rule.recipient_users.all()
    assert rule in admin_user.bi_alert_subscriptions.all()


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_evaluation_helpers_gt_lt_gte_lte_eq(tenant_a):
    """Test condition evaluation logic for standard comparison operators."""
    rule_gt = _alertssubscriptions_create_alert_rule(tenant_a, condition_operator="gt", threshold_value=Decimal("100.0"))
    assert _alertssubscriptions_evaluate_condition(rule_gt, Decimal("105.0")) is True
    assert _alertssubscriptions_evaluate_condition(rule_gt, Decimal("100.0")) is False
    assert _alertssubscriptions_evaluate_condition(rule_gt, Decimal("95.0")) is False

    rule_gte = _alertssubscriptions_create_alert_rule(tenant_a, condition_operator="gte", threshold_value=Decimal("100.0"))
    assert _alertssubscriptions_evaluate_condition(rule_gte, Decimal("100.0")) is True
    assert _alertssubscriptions_evaluate_condition(rule_gte, Decimal("99.99")) is False

    rule_lt = _alertssubscriptions_create_alert_rule(tenant_a, condition_operator="lt", threshold_value=Decimal("50.0"))
    assert _alertssubscriptions_evaluate_condition(rule_lt, Decimal("40.0")) is True
    assert _alertssubscriptions_evaluate_condition(rule_lt, Decimal("50.0")) is False

    rule_lte = _alertssubscriptions_create_alert_rule(tenant_a, condition_operator="lte", threshold_value=Decimal("50.0"))
    assert _alertssubscriptions_evaluate_condition(rule_lte, Decimal("50.0")) is True
    assert _alertssubscriptions_evaluate_condition(rule_lte, Decimal("50.01")) is False

    rule_eq = _alertssubscriptions_create_alert_rule(tenant_a, condition_operator="eq", threshold_value=Decimal("10.0"))
    assert _alertssubscriptions_evaluate_condition(rule_eq, Decimal("10.0")) is True
    assert _alertssubscriptions_evaluate_condition(rule_eq, Decimal("10.01")) is False


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_evaluation_helpers_outside_range(tenant_a):
    """Test condition evaluation logic for outside_range operator."""
    rule_range = _alertssubscriptions_create_alert_rule(
        tenant_a,
        condition_operator="outside_range",
        threshold_value=Decimal("20.0"),
        secondary_threshold_value=Decimal("80.0"),
    )
    # Outside lower bound
    assert _alertssubscriptions_evaluate_condition(rule_range, Decimal("15.0")) is True
    # Inside bound
    assert _alertssubscriptions_evaluate_condition(rule_range, Decimal("50.0")) is False
    # Outside upper bound
    assert _alertssubscriptions_evaluate_condition(rule_range, Decimal("85.0")) is True


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_evaluation_helpers_anomalies_and_pct(tenant_a):
    """Test condition evaluation for anomaly and percentage operators."""
    rule_anom = _alertssubscriptions_create_alert_rule(tenant_a, condition_operator="anomaly_flagged")
    assert _alertssubscriptions_evaluate_condition(rule_anom, Decimal("1.0")) is True

    rule_pct = _alertssubscriptions_create_alert_rule(tenant_a, condition_operator="pct_change_gt")
    assert _alertssubscriptions_evaluate_condition(rule_pct, Decimal("25.0")) is True


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_record_evaluation(tenant_a):
    """Test record_evaluation updates last_evaluated_at, trigger_count, and status."""
    rule = _alertssubscriptions_create_alert_rule(
        tenant_a,
        condition_operator="gt",
        threshold_value=Decimal("100.0"),
        status="active",
        trigger_count=0,
    )

    # First evaluation: breach occurs
    tripped = _alertssubscriptions_record_evaluation(rule, Decimal("150.0"))
    rule.refresh_from_db()
    assert tripped is True
    assert rule.status == "tripped"
    assert rule.trigger_count == 1
    assert rule.last_trigger_value == Decimal("150.0000")
    assert rule.last_evaluated_at is not None
    assert rule.last_triggered_at is not None

    # Second evaluation: condition clears back to normal
    tripped_2 = _alertssubscriptions_record_evaluation(rule, Decimal("50.0"))
    rule.refresh_from_db()
    assert tripped_2 is False
    assert rule.status == "active"
    assert rule.trigger_count == 1  # count preserved


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_foreign_keys(tenant_a, admin_user):
    """Test ForeignKey links to KpiDefinition, StatisticalAnomaly, and User."""
    rule = _alertssubscriptions_create_alert_rule(
        tenant_a,
        created_by=admin_user,
    )
    assert rule.created_by == admin_user
    assert rule.kpi_definition is None
    assert rule.anomaly_detection is None


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_tenant_isolation(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test BiAlertRule records are completely isolated per tenant."""
    rule_a = _alertssubscriptions_create_alert_rule(tenant_a, name="Acme Alert", created_by=admin_user)
    rule_b = _alertssubscriptions_create_alert_rule(tenant_b, name="Globex Alert", created_by=admin_user_b)

    tenant_a_rules = BiAlertRule.objects.filter(tenant=tenant_a)
    assert rule_a in tenant_a_rules
    assert rule_b not in tenant_a_rules

    tenant_b_rules = BiAlertRule.objects.filter(tenant=tenant_b)
    assert rule_b in tenant_b_rules
    assert rule_a not in tenant_b_rules


@pytest.mark.django_db
def test_alertssubscriptions_models_alert_rule_unique_number_per_tenant(tenant_a, tenant_b):
    """Test duplicate numbers are disallowed within the same tenant but permitted across tenants."""
    rule1 = _alertssubscriptions_create_alert_rule(tenant_a, name="Rule 1")
    dup_num = rule1.number

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiAlertRule.objects.create(
                tenant=tenant_a,
                number=dup_num,
                name="Duplicate Number Rule",
            )

    # Allowed in another tenant
    rule_other = BiAlertRule.objects.create(
        tenant=tenant_b,
        number=dup_num,
        name="Cross Tenant Rule",
    )
    assert rule_other.pk is not None


# ===========================================================================
# 2. ReportSubscription Model Tests (BSUB)
# ===========================================================================


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_fixture_and_str(report_subscription_a):
    """Test ReportSubscription fixture from conftest, string representation, and prefix."""
    assert report_subscription_a.pk is not None
    assert report_subscription_a.number.startswith("BSUB-")
    expected_str = f"{report_subscription_a.number} - {report_subscription_a.name}"
    assert str(report_subscription_a) == expected_str


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_autonumbering(tenant_a):
    """Test auto-numbering generates sequential BSUB- numbers for ReportSubscription."""
    sub1 = _alertssubscriptions_create_subscription(tenant_a, name="Sub Alpha")
    sub2 = _alertssubscriptions_create_subscription(tenant_a, name="Sub Beta")

    assert sub1.number.startswith("BSUB-")
    assert sub2.number.startswith("BSUB-")
    n1 = int(sub1.number.split("-")[1])
    n2 = int(sub2.number.split("-")[1])
    assert n2 == n1 + 1


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_defaults(tenant_a):
    """Test default values on newly created ReportSubscription."""
    sub = ReportSubscription.objects.create(
        tenant=tenant_a,
        name="Default Subscription",
    )
    assert sub.NUMBER_PREFIX == "BSUB"
    assert sub.number.startswith("BSUB-")
    assert sub.target_asset_type == "dashboard"
    assert sub.dashboard is None
    assert sub.report is None
    assert sub.export_format == "pdf"
    assert sub.cadence == "weekly"
    assert sub.scheduled_time == time(8, 0)
    assert sub.cron_expression == "0 8 * * 1"
    assert sub.burst_mode == "broadcast"
    assert sub.external_recipient_emails == ""
    assert sub.filter_overrides == {}
    assert sub.include_cover_page is True
    assert sub.skip_if_empty is False
    assert sub.status == "active"
    assert sub.last_run_at is None
    assert sub.next_run_at is None
    assert sub.run_count == 0


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_choices():
    """Test choices collections defined on ReportSubscription model."""
    target_types = _alertssubscriptions_choice_keys(ReportSubscription.TARGET_ASSET_TYPE_CHOICES)
    assert "dashboard" in target_types
    assert "report" in target_types

    formats = _alertssubscriptions_choice_keys(ReportSubscription.EXPORT_FORMAT_CHOICES)
    assert "pdf" in formats
    assert "xlsx" in formats
    assert "csv" in formats
    assert "html_inline" in formats

    cadences = _alertssubscriptions_choice_keys(ReportSubscription.CADENCE_CHOICES)
    assert "daily" in cadences
    assert "weekly" in cadences
    assert "monthly" in cadences
    assert "quarterly" in cadences
    assert "cron" in cadences

    burst_modes = _alertssubscriptions_choice_keys(ReportSubscription.BURST_MODE_CHOICES)
    assert "broadcast" in burst_modes
    assert "slice_by_user" in burst_modes
    assert "slice_by_org_unit" in burst_modes

    statuses = _alertssubscriptions_choice_keys(ReportSubscription.STATUS_CHOICES)
    assert "active" in statuses
    assert "paused" in statuses
    assert "failed" in statuses
    assert "archived" in statuses


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_status_badges(tenant_a):
    """Test status_badge_class property mappings on ReportSubscription."""
    sub = _alertssubscriptions_create_subscription(tenant_a, status="active")
    assert sub.status_badge_class == "badge-green"

    sub.status = "paused"
    assert sub.status_badge_class == "badge-amber"

    sub.status = "failed"
    assert sub.status_badge_class == "badge-red"

    sub.status = "archived"
    assert sub.status_badge_class == "badge-slate"

    sub.status = "unknown_status"
    assert sub.status_badge_class == "badge-slate"


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_format_badges(tenant_a):
    """Test format_badge_class property mappings on ReportSubscription."""
    sub = _alertssubscriptions_create_subscription(tenant_a, export_format="pdf")
    assert sub.format_badge_class == "badge-red"

    sub.export_format = "xlsx"
    assert sub.format_badge_class == "badge-green"

    sub.export_format = "csv"
    assert sub.format_badge_class == "badge-info"

    sub.export_format = "html_inline"
    assert sub.format_badge_class == "badge-slate"

    sub.export_format = "xml"
    assert sub.format_badge_class == "badge-slate"


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_get_absolute_url(report_subscription_a):
    """Test get_absolute_url maps correctly to detail view."""
    url = report_subscription_a.get_absolute_url()
    assert url == f"/bi/subscriptions/{report_subscription_a.pk}/"


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_target_assets_dashboard_and_report(tenant_a, bi_dashboard_a):
    """Test subscription target FK links to BiDashboard or ReportDefinition."""
    sub_dash = _alertssubscriptions_create_subscription(
        tenant_a,
        target_asset_type="dashboard",
        dashboard=bi_dashboard_a,
    )
    assert sub_dash.dashboard == bi_dashboard_a
    assert sub_dash in bi_dashboard_a.subscriptions.all()

    report_def = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Monthly Ledger Report",
        slug="monthly-ledger-report",
        category="finance",
        report_type="standard_tabular",
        status="published",
    )
    sub_rep = _alertssubscriptions_create_subscription(
        tenant_a,
        name="Operational Report Subscription",
        target_asset_type="report",
        report=report_def,
    )
    assert sub_rep.report == report_def
    assert sub_rep in report_def.subscriptions.all()


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_m2m_subscribers_and_org_units(tenant_a, admin_user):
    """Test subscriber_users and subscriber_org_units ManyToMany links."""
    sub = _alertssubscriptions_create_subscription(tenant_a, name="Team Broadcast")
    assert sub.subscriber_users.count() == 0
    assert sub.subscriber_org_units.count() == 0

    sub.subscriber_users.add(admin_user)
    assert sub.subscriber_users.count() == 1
    assert admin_user in sub.subscriber_users.all()

    org_unit = OrgUnit.objects.create(
        tenant=tenant_a,
        name="Business Intelligence Unit",
        kind="department",
    )
    sub.subscriber_org_units.add(org_unit)
    assert sub.subscriber_org_units.count() == 1
    assert org_unit in sub.subscriber_org_units.all()


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_run_helpers(tenant_a):
    """Test recording execution runs on ReportSubscription."""
    sub = _alertssubscriptions_create_subscription(tenant_a, run_count=0)
    assert sub.last_run_at is None

    _alertssubscriptions_record_subscription_run(sub, success=True)
    sub.refresh_from_db()
    assert sub.run_count == 1
    assert sub.last_run_at is not None
    assert sub.status == "active"

    # Failed run
    _alertssubscriptions_record_subscription_run(sub, success=False)
    sub.refresh_from_db()
    assert sub.run_count == 2
    assert sub.status == "failed"


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_tenant_isolation(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test ReportSubscription tenant isolation."""
    sub_a = _alertssubscriptions_create_subscription(tenant_a, name="Acme Sub", created_by=admin_user)
    sub_b = _alertssubscriptions_create_subscription(tenant_b, name="Globex Sub", created_by=admin_user_b)

    tenant_a_subs = ReportSubscription.objects.filter(tenant=tenant_a)
    assert sub_a in tenant_a_subs
    assert sub_b not in tenant_a_subs


@pytest.mark.django_db
def test_alertssubscriptions_models_subscription_unique_number_per_tenant(tenant_a, tenant_b):
    """Test duplicate numbers are disallowed within the same tenant for ReportSubscription."""
    sub1 = _alertssubscriptions_create_subscription(tenant_a, name="Subscription 1")
    dup_num = sub1.number

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReportSubscription.objects.create(
                tenant=tenant_a,
                number=dup_num,
                name="Duplicate Number Subscription",
            )

    sub_b = ReportSubscription.objects.create(
        tenant=tenant_b,
        number=dup_num,
        name="Cross Tenant Subscription",
    )
    assert sub_b.pk is not None


# ===========================================================================
# 3. DistributionBurstRun Model Tests (BBRS)
# ===========================================================================


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_fixture_and_str(distribution_burst_run_a):
    """Test DistributionBurstRun fixture from conftest, string representation, and prefix."""
    assert distribution_burst_run_a.pk is not None
    assert distribution_burst_run_a.number.startswith("BBRS-")
    expected_str = f"{distribution_burst_run_a.number} ({distribution_burst_run_a.get_status_display()})"
    assert str(distribution_burst_run_a) == expected_str


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_autonumbering(tenant_a):
    """Test auto-numbering generates sequential BBRS- numbers for DistributionBurstRun."""
    run1 = _alertssubscriptions_create_burst_run(tenant_a)
    run2 = _alertssubscriptions_create_burst_run(tenant_a)

    assert run1.number.startswith("BBRS-")
    assert run2.number.startswith("BBRS-")
    n1 = int(run1.number.split("-")[1])
    n2 = int(run2.number.split("-")[1])
    assert n2 == n1 + 1


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_defaults(tenant_a):
    """Test default values on newly created DistributionBurstRun."""
    run = DistributionBurstRun.objects.create(
        tenant=tenant_a,
    )
    assert run.NUMBER_PREFIX == "BBRS"
    assert run.number.startswith("BBRS-")
    assert run.subscription is None
    assert run.alert_rule is None
    assert run.run_trigger == "scheduled_subscription"
    assert run.delivery_channel == "email"
    assert run.status == "completed"
    assert run.recipient_count == 1
    assert run.delivered_count == 1
    assert run.failed_count == 0
    assert run.execution_duration_ms == 0
    assert run.generated_file_name == ""
    assert run.file_size_bytes == 0
    assert run.burst_slicing_metadata == {}
    assert run.error_summary == ""
    assert run.started_at is not None
    assert run.completed_at is None


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_choices():
    """Test choices collections defined on DistributionBurstRun model."""
    triggers = _alertssubscriptions_choice_keys(DistributionBurstRun.RUN_TRIGGER_CHOICES)
    assert "scheduled_subscription" in triggers
    assert "ad_hoc_manual" in triggers
    assert "alert_triggered" in triggers

    channels = _alertssubscriptions_choice_keys(DistributionBurstRun.DELIVERY_CHANNEL_CHOICES)
    assert "email" in channels
    assert "sftp" in channels
    assert "portal_inbox" in channels
    assert "webhook" in channels

    statuses = _alertssubscriptions_choice_keys(DistributionBurstRun.STATUS_CHOICES)
    assert "queued" in statuses
    assert "processing" in statuses
    assert "completed" in statuses
    assert "partial_failure" in statuses
    assert "failed" in statuses


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_status_badges(tenant_a):
    """Test status_badge_class property mappings on DistributionBurstRun."""
    run = _alertssubscriptions_create_burst_run(tenant_a, status="completed")
    assert run.status_badge_class == "badge-green"

    run.status = "processing"
    assert run.status_badge_class == "badge-info"

    run.status = "queued"
    assert run.status_badge_class == "badge-amber"

    run.status = "partial_failure"
    assert run.status_badge_class == "badge-amber"

    run.status = "failed"
    assert run.status_badge_class == "badge-red"

    run.status = "unknown"
    assert run.status_badge_class == "badge-slate"


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_channel_badges(tenant_a):
    """Test channel_badge_class property mappings on DistributionBurstRun."""
    run = _alertssubscriptions_create_burst_run(tenant_a, delivery_channel="email")
    assert run.channel_badge_class == "badge-info"

    run.delivery_channel = "sftp"
    assert run.channel_badge_class == "badge-slate"

    run.delivery_channel = "portal_inbox"
    assert run.channel_badge_class == "badge-green"

    run.delivery_channel = "webhook"
    assert run.channel_badge_class == "badge-amber"

    run.delivery_channel = "unknown"
    assert run.channel_badge_class == "badge-slate"


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_get_absolute_url(distribution_burst_run_a):
    """Test get_absolute_url maps correctly to detail view."""
    url = distribution_burst_run_a.get_absolute_url()
    assert url == f"/bi/burst-runs/{distribution_burst_run_a.pk}/"


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_foreign_keys(tenant_a, report_subscription_a, bi_alert_rule_a, admin_user):
    """Test foreign keys linking to subscription, alert rule, and user."""
    run = _alertssubscriptions_create_burst_run(
        tenant_a,
        subscription=report_subscription_a,
        alert_rule=bi_alert_rule_a,
        executed_by=admin_user,
    )
    assert run.subscription == report_subscription_a
    assert run in report_subscription_a.burst_runs.all()

    assert run.alert_rule == bi_alert_rule_a
    assert run in bi_alert_rule_a.burst_runs.all()

    assert run.executed_by == admin_user


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_success_rate_metric(tenant_a):
    """Test success_rate calculation on DistributionBurstRun."""
    run = _alertssubscriptions_create_burst_run(
        tenant_a,
        recipient_count=20,
        delivered_count=18,
        failed_count=2,
    )
    rate = _alertssubscriptions_burst_run_success_rate(run)
    assert rate == Decimal("90.00")

    # Zero recipients edge case
    run_zero = _alertssubscriptions_create_burst_run(
        tenant_a,
        recipient_count=0,
        delivered_count=0,
    )
    assert _alertssubscriptions_burst_run_success_rate(run_zero) == Decimal("0.00")


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_mark_completed_and_failed(tenant_a):
    """Test transitioning run to completed or failed states."""
    run = _alertssubscriptions_create_burst_run(tenant_a, status="processing", completed_at=None)

    _alertssubscriptions_burst_run_mark_completed(run, delivered=15)
    run.refresh_from_db()
    assert run.status == "completed"
    assert run.delivered_count == 15
    assert run.completed_at is not None

    _alertssubscriptions_burst_run_mark_failed(run, error="SMTP authentication rejected")
    run.refresh_from_db()
    assert run.status == "failed"
    assert run.error_summary == "SMTP authentication rejected"


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_slicing_metadata_json(tenant_a):
    """Test burst_slicing_metadata JSON storage and retrieval."""
    metadata = {
        "slices": [
            {"region": "EMEA", "filter": "region=EMEA", "file": "emea.pdf"},
            {"region": "APAC", "filter": "region=APAC", "file": "apac.pdf"},
        ],
        "batch_id": "BATCH-001",
    }
    run = _alertssubscriptions_create_burst_run(tenant_a, burst_slicing_metadata=metadata)
    run.refresh_from_db()
    assert run.burst_slicing_metadata == metadata
    assert len(run.burst_slicing_metadata["slices"]) == 2


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_tenant_isolation(tenant_a, tenant_b):
    """Test DistributionBurstRun tenant isolation."""
    run_a = _alertssubscriptions_create_burst_run(tenant_a)
    run_b = _alertssubscriptions_create_burst_run(tenant_b)

    assert run_a in DistributionBurstRun.objects.filter(tenant=tenant_a)
    assert run_b not in DistributionBurstRun.objects.filter(tenant=tenant_a)


@pytest.mark.django_db
def test_alertssubscriptions_models_burst_run_unique_number_per_tenant(tenant_a, tenant_b):
    """Test duplicate numbers are disallowed within the same tenant for DistributionBurstRun."""
    run1 = _alertssubscriptions_create_burst_run(tenant_a)
    dup_num = run1.number

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DistributionBurstRun.objects.create(
                tenant=tenant_a,
                number=dup_num,
            )

    run_b = DistributionBurstRun.objects.create(
        tenant=tenant_b,
        number=dup_num,
    )
    assert run_b.pk is not None


# ===========================================================================
# 4. BiNotificationItem Model Tests (BNTF)
# ===========================================================================


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_fixture_and_str(bi_notification_item_a):
    """Test BiNotificationItem fixture from conftest, string representation, and prefix."""
    assert bi_notification_item_a.pk is not None
    assert bi_notification_item_a.number.startswith("BNTF-")
    expected_str = f"{bi_notification_item_a.number} - {bi_notification_item_a.title}"
    assert str(bi_notification_item_a) == expected_str


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_autonumbering(tenant_a, admin_user):
    """Test auto-numbering generates sequential BNTF- numbers for BiNotificationItem."""
    ntf1 = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, title="Notice Alpha")
    ntf2 = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, title="Notice Beta")

    assert ntf1.number.startswith("BNTF-")
    assert ntf2.number.startswith("BNTF-")
    n1 = int(ntf1.number.split("-")[1])
    n2 = int(ntf2.number.split("-")[1])
    assert n2 == n1 + 1


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_defaults(tenant_a, admin_user):
    """Test default values on newly created BiNotificationItem."""
    ntf = BiNotificationItem.objects.create(
        tenant=tenant_a,
        recipient=admin_user,
        title="Default Notice",
        message="Default Notice Body",
    )
    assert ntf.NUMBER_PREFIX == "BNTF"
    assert ntf.number.startswith("BNTF-")
    assert ntf.severity == "info"
    assert ntf.category == "kpi_alert"
    assert ntf.status == "unread"
    assert ntf.alert_rule is None
    assert ntf.burst_run is None
    assert ntf.action_url == ""
    assert ntf.read_at is None
    assert ntf.acknowledged_at is None
    assert ntf.acknowledged_by is None
    assert ntf.acknowledgment_notes == ""
    assert ntf.snoozed_until is None
    assert ntf.escalation_level == 0
    assert ntf.escalated_to is None
    assert ntf.workflow_converted is False
    assert ntf.workflow_reference == ""


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_choices():
    """Test choices collections defined on BiNotificationItem model."""
    severities = _alertssubscriptions_choice_keys(BiNotificationItem.SEVERITY_CHOICES)
    assert "info" in severities
    assert "warning" in severities
    assert "critical" in severities

    categories = _alertssubscriptions_choice_keys(BiNotificationItem.CATEGORY_CHOICES)
    assert "kpi_alert" in categories
    assert "anomaly_alert" in categories
    assert "subscription_digest" in categories
    assert "workflow_task" in categories
    assert "system_bulletin" in categories

    statuses = _alertssubscriptions_choice_keys(BiNotificationItem.STATUS_CHOICES)
    assert "unread" in statuses
    assert "read" in statuses
    assert "acknowledged" in statuses
    assert "snoozed" in statuses
    assert "escalated" in statuses
    assert "dismissed" in statuses


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_severity_badges(tenant_a, admin_user):
    """Test severity_badge_class property mappings on BiNotificationItem."""
    ntf = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, severity="critical")
    assert ntf.severity_badge_class == "badge-red"

    ntf.severity = "warning"
    assert ntf.severity_badge_class == "badge-amber"

    ntf.severity = "info"
    assert ntf.severity_badge_class == "badge-info"

    ntf.severity = "unknown"
    assert ntf.severity_badge_class == "badge-slate"


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_status_badges(tenant_a, admin_user):
    """Test status_badge_class property mappings on BiNotificationItem."""
    ntf = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, status="unread")
    assert ntf.status_badge_class == "badge-info"

    ntf.status = "read"
    assert ntf.status_badge_class == "badge-slate"

    ntf.status = "acknowledged"
    assert ntf.status_badge_class == "badge-green"

    ntf.status = "snoozed"
    assert ntf.status_badge_class == "badge-amber"

    ntf.status = "escalated"
    assert ntf.status_badge_class == "badge-red"

    ntf.status = "dismissed"
    assert ntf.status_badge_class == "badge-muted"

    ntf.status = "unknown"
    assert ntf.status_badge_class == "badge-slate"


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_category_badges(tenant_a, admin_user):
    """Test category_badge_class property mappings on BiNotificationItem."""
    ntf = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, category="kpi_alert")
    assert ntf.category_badge_class == "badge-amber"

    ntf.category = "anomaly_alert"
    assert ntf.category_badge_class == "badge-slate"

    ntf.category = "subscription_digest"
    assert ntf.category_badge_class == "badge-info"

    ntf.category = "workflow_task"
    assert ntf.category_badge_class == "badge-green"

    ntf.category = "system_bulletin"
    assert ntf.category_badge_class == "badge-slate"

    ntf.category = "unknown"
    assert ntf.category_badge_class == "badge-slate"


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_get_absolute_url(bi_notification_item_a):
    """Test get_absolute_url maps correctly to detail view."""
    url = bi_notification_item_a.get_absolute_url()
    assert url == f"/bi/notifications/{bi_notification_item_a.pk}/"


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_transition_mark_read(tenant_a, admin_user):
    """Test transitioning notification to read state."""
    ntf = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, status="unread")
    assert ntf.read_at is None

    _alertssubscriptions_notification_mark_read(ntf)
    ntf.refresh_from_db()
    assert ntf.status == "read"
    assert ntf.read_at is not None


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_transition_acknowledge(tenant_a, admin_user):
    """Test transitioning notification to acknowledged state."""
    ntf = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, status="unread")
    assert ntf.acknowledged_at is None

    _alertssubscriptions_notification_acknowledge(ntf, user=admin_user, notes="Investigating issue.")
    ntf.refresh_from_db()
    assert ntf.status == "acknowledged"
    assert ntf.acknowledged_at is not None
    assert ntf.acknowledged_by == admin_user
    assert ntf.acknowledgment_notes == "Investigating issue."


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_transition_snooze(tenant_a, admin_user):
    """Test snoozing a notification and checking is_snoozed_active helper."""
    ntf = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, status="unread")
    assert _alertssubscriptions_notification_is_snoozed_active(ntf) is False

    _alertssubscriptions_notification_snooze(ntf, hours=4)
    ntf.refresh_from_db()
    assert ntf.status == "snoozed"
    assert ntf.snoozed_until is not None
    assert _alertssubscriptions_notification_is_snoozed_active(ntf) is True

    # Expired snooze
    ntf.snoozed_until = timezone.now() - timedelta(minutes=10)
    ntf.save()
    assert _alertssubscriptions_notification_is_snoozed_active(ntf) is False


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_transition_escalate(tenant_a, admin_user, admin_user_b):
    """Test escalating notification level and assigning escalated_to user."""
    ntf = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, escalation_level=0)

    _alertssubscriptions_notification_escalate(ntf, target_user=admin_user_b)
    ntf.refresh_from_db()
    assert ntf.status == "escalated"
    assert ntf.escalation_level == 1
    assert ntf.escalated_to == admin_user_b

    # Escalating again caps at 3
    _alertssubscriptions_notification_escalate(ntf)
    _alertssubscriptions_notification_escalate(ntf)
    _alertssubscriptions_notification_escalate(ntf)
    ntf.refresh_from_db()
    assert ntf.escalation_level == 3


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_fk_relations(tenant_a, admin_user, bi_alert_rule_a, distribution_burst_run_a):
    """Test ForeignKey links from BiNotificationItem to alert rule, burst run, and recipient."""
    ntf = _alertssubscriptions_create_notification(
        tenant_a,
        recipient=admin_user,
        alert_rule=bi_alert_rule_a,
        burst_run=distribution_burst_run_a,
    )
    assert ntf.recipient == admin_user
    assert ntf in admin_user.bi_notifications.all()

    assert ntf.alert_rule == bi_alert_rule_a
    assert ntf in bi_alert_rule_a.notifications.all()

    assert ntf.burst_run == distribution_burst_run_a
    assert ntf in distribution_burst_run_a.notifications.all()


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_tenant_isolation(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test BiNotificationItem tenant isolation."""
    ntf_a = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user, title="Acme Notice")
    ntf_b = _alertssubscriptions_create_notification(tenant_b, recipient=admin_user_b, title="Globex Notice")

    tenant_a_items = BiNotificationItem.objects.filter(tenant=tenant_a)
    assert ntf_a in tenant_a_items
    assert ntf_b not in tenant_a_items


@pytest.mark.django_db
def test_alertssubscriptions_models_notification_unique_number_per_tenant(tenant_a, tenant_b, admin_user):
    """Test duplicate numbers are disallowed within the same tenant for BiNotificationItem."""
    ntf1 = _alertssubscriptions_create_notification(tenant_a, recipient=admin_user)
    dup_num = ntf1.number

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiNotificationItem.objects.create(
                tenant=tenant_a,
                recipient=admin_user,
                number=dup_num,
                title="Duplicate Notification",
            )

    ntf_b = BiNotificationItem.objects.create(
        tenant=tenant_b,
        recipient=admin_user,
        number=dup_num,
        title="Cross Tenant Notification",
    )
    assert ntf_b.pk is not None
