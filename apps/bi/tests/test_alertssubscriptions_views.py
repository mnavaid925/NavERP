"""View test suite for Sub-module 10.16: Alerts, Subscriptions & Distribution (apps/bi).

Views and Workspaces covered:
1. BiAlertRule views:
   - bi_alert_rule_list and alias alert_rule_list (200, stats, search, filters, pagination, empty state)
   - bi_alert_rule_create and alias alert_rule_create (GET 200, POST valid -> 302, POST invalid -> 200)
   - bi_alert_rule_detail and alias alert_rule_detail (GET 200, None-safe render)
   - bi_alert_rule_edit and alias alert_rule_edit (GET 200, POST valid -> 302, POST invalid -> 200)
   - bi_alert_rule_delete and alias alert_rule_delete (POST 302, GET 405, non-admin 403)
   - bi_alert_rule_test_evaluate and alias alert_rule_test_evaluate (POST 302 evaluate tripped/normal, GET 405)

2. ReportSubscription views:
   - report_subscription_list (200, stats, search, filters, pagination, empty state)
   - report_subscription_create (GET 200, POST valid -> 302, POST invalid -> 200)
   - report_subscription_detail (GET 200, None-safe render when created_by=None)
   - report_subscription_edit (GET 200, POST valid -> 302, POST invalid -> 200)
   - report_subscription_delete (POST 302, GET 405, non-admin 403)
   - report_subscription_run_now (POST 302 spawns burst run and updates subscription, GET 405)

3. DistributionBurstRun views:
   - distribution_burst_run_list (200, stats, search, filters, pagination, empty state)
   - distribution_burst_run_create (GET 200, POST valid -> 302, POST invalid -> 200)
   - distribution_burst_run_detail (GET 200, None-safe render)
   - distribution_burst_run_edit (GET 200, POST valid -> 302, POST invalid -> 200)
   - distribution_burst_run_delete (POST 302, GET 405, non-admin 403)

4. BiNotificationItem views & Notification Center workspace:
   - bi_notification_item_list and alias notification_item_list (200, stats, search, filters, pagination, empty state)
   - bi_notification_item_create and alias notification_item_create (GET 200, POST valid -> 302, POST invalid -> 200)
   - bi_notification_item_detail and alias notification_item_detail (GET 200, auto-marks unread as read for recipient)
   - bi_notification_item_edit and alias notification_item_edit (GET 200, POST valid -> 302, POST invalid -> 200)
   - bi_notification_item_delete and alias notification_item_delete (POST 302, GET 405)
   - notification_center workspace (GET 200, tabs: all, unread, critical, snoozed, escalated, category filter, user scoping)
   - notification_mark_read (POST 302, GET 405)
   - notification_acknowledge (POST 302 with notes, GET 405)
   - notification_snooze (POST 302 with hours validation 1, 4, 24, 72, and invalid fallback, GET 405)
   - notification_escalate (POST 302 with level increment clamped at 3, GET 405)

5. Cross-Tenant Isolation & Unauthenticated Access:
   - Cross-tenant IDOR 404 for all entities
   - Anonymous access 302 redirects to login
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
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
from apps.core.models import AuditLog, OrgUnit

User = get_user_model()


# ==============================================================================
# Module Helpers (strictly prefixed with _alertssubscriptions_)
# ==============================================================================


def _alertssubscriptions_create_alert_rule(tenant, user=None, **kwargs):
    """Helper to create a tenant-scoped BiAlertRule."""
    defaults = {
        "tenant": tenant,
        "name": f"Helper Alert Rule {timezone.now().timestamp()}",
        "alert_type": "kpi_threshold",
        "condition_operator": "gt",
        "threshold_value": Decimal("100.0000"),
        "severity": "critical",
        "evaluation_cadence": "hourly",
        "trigger_frequency": "every_time",
        "delivery_channel": "in_app_email",
        "status": "active",
        "created_by": user,
    }
    defaults.update(kwargs)
    rule = BiAlertRule.objects.create(**defaults)
    if user:
        rule.recipient_users.add(user)
    return rule


def _alertssubscriptions_create_subscription(tenant, dashboard=None, report=None, user=None, **kwargs):
    """Helper to create a tenant-scoped ReportSubscription."""
    defaults = {
        "tenant": tenant,
        "name": f"Helper Subscription {timezone.now().timestamp()}",
        "target_asset_type": "dashboard" if dashboard else ("report" if report else "dashboard"),
        "dashboard": dashboard,
        "report": report,
        "export_format": "pdf",
        "cadence": "weekly",
        "burst_mode": "broadcast",
        "status": "active",
        "include_cover_page": True,
        "created_by": user,
    }
    defaults.update(kwargs)
    sub = ReportSubscription.objects.create(**defaults)
    if user:
        sub.subscriber_users.add(user)
    return sub


def _alertssubscriptions_create_burst_run(tenant, subscription=None, alert_rule=None, user=None, **kwargs):
    """Helper to create a tenant-scoped DistributionBurstRun."""
    defaults = {
        "tenant": tenant,
        "subscription": subscription,
        "alert_rule": alert_rule,
        "run_trigger": "scheduled_subscription",
        "delivery_channel": "email",
        "status": "completed",
        "recipient_count": 5,
        "delivered_count": 5,
        "failed_count": 0,
        "executed_by": user,
        "started_at": timezone.now(),
        "completed_at": timezone.now(),
    }
    defaults.update(kwargs)
    return DistributionBurstRun.objects.create(**defaults)


def _alertssubscriptions_create_notification_item(tenant, recipient, alert_rule=None, burst_run=None, **kwargs):
    """Helper to create a tenant-scoped BiNotificationItem."""
    defaults = {
        "tenant": tenant,
        "recipient": recipient,
        "title": f"Helper Notification {timezone.now().timestamp()}",
        "message": "Helper operational alert message content.",
        "severity": "info",
        "category": "kpi_alert",
        "status": "unread",
        "alert_rule": alert_rule,
        "burst_run": burst_run,
    }
    defaults.update(kwargs)
    return BiNotificationItem.objects.create(**defaults)


def _alertssubscriptions_valid_alert_rule_data(kpi_definition=None, anomaly_detection=None, recipient_users=None, **kwargs):
    """Helper returning a valid data payload for BiAlertRule form."""
    data = {
        "name": "Operating Margin Threshold Alert",
        "description": "Trigger alert if operating margin dips below target floor.",
        "alert_type": "kpi_threshold",
        "condition_operator": "lt",
        "threshold_value": "0.1500",
        "secondary_threshold_value": "0.2500",
        "severity": "critical",
        "evaluation_cadence": "hourly",
        "trigger_frequency": "once_until_resolved",
        "delivery_channel": "in_app_email",
        "notification_email_list": "ops@acme.com, alerts@acme.com",
        "webhook_url": "https://hooks.slack.com/services/T00/B00/X00",
        "downstream_workflow": "create_task",
        "status": "active",
    }
    if kpi_definition:
        data["kpi_definition"] = str(kpi_definition.pk)
    if anomaly_detection:
        data["anomaly_detection"] = str(anomaly_detection.pk)
    if recipient_users:
        data["recipient_users"] = [str(u.pk) for u in recipient_users]
    data.update(kwargs)
    return data


def _alertssubscriptions_valid_subscription_data(dashboard=None, report=None, subscriber_users=None, subscriber_org_units=None, **kwargs):
    """Helper returning a valid data payload for ReportSubscription form."""
    data = {
        "name": "Weekly Monday Executive Digest",
        "target_asset_type": "dashboard",
        "export_format": "pdf",
        "cadence": "weekly",
        "scheduled_time": "08:00",
        "cron_expression": "0 8 * * 1",
        "burst_mode": "broadcast",
        "external_recipient_emails": "execs@acme.com, board@acme.com",
        "include_cover_page": True,
        "skip_if_empty": True,
        "status": "active",
    }
    if dashboard:
        data["dashboard"] = str(dashboard.pk)
    if report:
        data["report"] = str(report.pk)
    if subscriber_users:
        data["subscriber_users"] = [str(u.pk) for u in subscriber_users]
    if subscriber_org_units:
        data["subscriber_org_units"] = [str(ou.pk) for ou in subscriber_org_units]
    data.update(kwargs)
    return data


def _alertssubscriptions_valid_burst_run_data(subscription=None, alert_rule=None, **kwargs):
    """Helper returning a valid data payload for DistributionBurstRun form."""
    data = {
        "run_trigger": "scheduled_subscription",
        "delivery_channel": "email",
        "status": "completed",
        "recipient_count": 12,
        "generated_file_name": "Weekly_Exec_Digest_20261108.pdf",
        "file_size_bytes": 1048576,
        "error_summary": "All 12 recipients dispatched with zero delivery failures.",
    }
    if subscription:
        data["subscription"] = str(subscription.pk)
    if alert_rule:
        data["alert_rule"] = str(alert_rule.pk)
    data.update(kwargs)
    return data


def _alertssubscriptions_valid_notification_data(recipient, alert_rule=None, burst_run=None, **kwargs):
    """Helper returning a valid data payload for BiNotificationItem form."""
    data = {
        "recipient": str(recipient.pk),
        "title": "Operating Margin Threshold Tripped",
        "message": "Current margin 12.4% fell below target 15.0%.",
        "severity": "critical",
        "category": "kpi_alert",
        "status": "unread",
        "action_url": "/bi/dashboards/1/",
        "acknowledgment_notes": "Reviewed by on-call ops engineer.",
        "snoozed_until": "2026-11-10T12:00:00",
    }
    if alert_rule:
        data["alert_rule"] = str(alert_rule.pk)
    if burst_run:
        data["burst_run"] = str(burst_run.pk)
    data.update(kwargs)
    return data


# ==============================================================================
# 1. BiAlertRule View Tests
# ==============================================================================


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_list_get_and_stats(
    client_a, bi_alert_rule_a, bi_alert_rule_b
):
    """Test alert rule list view returns 200, context statistics, and filters by tenant."""
    url = reverse("bi:bi_alert_rule_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "rules" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["active_count"] >= 1
    assert "tripped_count" in resp.context
    assert "critical_count" in resp.context
    assert "alert_type_choices" in resp.context
    assert "severity_choices" in resp.context
    assert "status_choices" in resp.context

    # Verify tenant isolation in list
    item_pks = [r.pk for r in resp.context["rules"]]
    assert bi_alert_rule_a.pk in item_pks
    assert bi_alert_rule_b.pk not in item_pks

    # Verify short alias alert_rule_list also returns 200
    alias_url = reverse("bi:alert_rule_list")
    resp_alias = client_a.get(alias_url)
    assert resp_alias.status_code == 200


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_list_search(
    client_a, tenant_a, admin_user
):
    """Test searching alert rule list by name, number, description, or notification email."""
    rule = _alertssubscriptions_create_alert_rule(
        tenant_a,
        user=admin_user,
        name="UniqueAlertAlphaKeyword",
        description="Detailed diagnostic threshold trigger description",
        notification_email_list="special-alpha-notify@acme.com",
    )
    url = reverse("bi:bi_alert_rule_list")

    # Positive search by name
    resp_name = client_a.get(url, {"q": "AlphaKeyword"})
    assert resp_name.status_code == 200
    assert any(r.pk == rule.pk for r in resp_name.context["rules"])

    # Positive search by email
    resp_email = client_a.get(url, {"q": "special-alpha-notify"})
    assert resp_email.status_code == 200
    assert any(r.pk == rule.pk for r in resp_email.context["rules"])

    # Negative search
    resp_neg = client_a.get(url, {"q": "NonExistentZetaRule999"})
    assert resp_neg.status_code == 200
    assert not any(r.pk == rule.pk for r in resp_neg.context["rules"])


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_list_filters(
    client_a, tenant_a, admin_user
):
    """Test filtering alert rules by status, alert_type, and severity."""
    rule = _alertssubscriptions_create_alert_rule(
        tenant_a,
        user=admin_user,
        name="Warning Anomaly Rule",
        alert_type="anomaly_detection",
        severity="warning",
        status="paused",
    )
    url = reverse("bi:bi_alert_rule_list")

    # Filter by status
    resp_status = client_a.get(url, {"status": "paused"})
    assert resp_status.status_code == 200
    assert all(r.status == "paused" for r in resp_status.context["rules"])

    # Filter by alert_type
    resp_type = client_a.get(url, {"alert_type": "anomaly_detection"})
    assert resp_type.status_code == 200
    assert all(r.alert_type == "anomaly_detection" for r in resp_type.context["rules"])

    # Filter by severity
    resp_sev = client_a.get(url, {"severity": "warning"})
    assert resp_sev.status_code == 200
    assert all(r.severity == "warning" for r in resp_sev.context["rules"])


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test pagination handles page splits at page size 15."""
    bulk = [
        BiAlertRule(
            tenant=tenant_a,
            number=f"BALR-PAG-{i:05d}",
            name=f"Paginated Rule {i}",
            alert_type="kpi_threshold",
            condition_operator="gt",
            threshold_value=Decimal("100.0000"),
            severity="info",
            status="active",
            created_by=admin_user,
        )
        for i in range(16)
    ]
    BiAlertRule.objects.bulk_create(bulk)

    url = reverse("bi:bi_alert_rule_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["rules"]) == 15

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["rules"]) >= 1


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_list_empty(client_a, tenant_a):
    """Test empty state when tenant has no alert rules."""
    BiAlertRule.objects.filter(tenant=tenant_a).delete()
    url = reverse("bi:bi_alert_rule_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["total_count"] == 0
    assert len(resp.context["rules"]) == 0


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_create_get(client_a):
    """Test create view GET returns 200 with form and context choices."""
    url = reverse("bi:bi_alert_rule_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["rule"] is None
    assert "users" in resp.context
    assert "kpi_definitions" in resp.context
    assert "anomalies" in resp.context

    # Alias check
    alias_url = reverse("bi:alert_rule_create")
    resp_alias = client_a.get(alias_url)
    assert resp_alias.status_code == 200


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_create_post_valid(
    client_a, tenant_a, admin_user
):
    """Test create view POST with valid data creates rule, logs audit, and redirects."""
    url = reverse("bi:bi_alert_rule_create")
    payload = _alertssubscriptions_valid_alert_rule_data(
        name="POST Created Alert Rule",
        threshold_value="500.0000",
        recipient_users=[admin_user],
    )
    resp = client_a.post(url, data=payload)

    assert resp.status_code == 302
    created = BiAlertRule.objects.filter(name="POST Created Alert Rule", tenant=tenant_a).first()
    assert created is not None
    assert created.created_by == admin_user
    assert resp.url == reverse("bi:bi_alert_rule_detail", kwargs={"pk": created.pk})

    # Verify audit log
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_create_post_valid_alias(
    client_a, tenant_a, admin_user
):
    """Test create view alias alert_rule_create POST functions identically."""
    alias_url = reverse("bi:alert_rule_create")
    payload = _alertssubscriptions_valid_alert_rule_data(
        name="POST Alias Created Rule",
    )
    resp = client_a.post(alias_url, data=payload)
    assert resp.status_code == 302
    created = BiAlertRule.objects.filter(name="POST Alias Created Rule", tenant=tenant_a).first()
    assert created is not None
    assert resp.url == reverse("bi:bi_alert_rule_detail", kwargs={"pk": created.pk})


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_create_post_invalid(client_a):
    """Test create view POST with invalid data re-renders form with errors."""
    url = reverse("bi:bi_alert_rule_create")
    resp = client_a.post(url, data={})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_detail_get(
    client_a, bi_alert_rule_a
):
    """Test alert rule detail view returns 200 with rule and recent notifications."""
    url = reverse("bi:bi_alert_rule_detail", kwargs={"pk": bi_alert_rule_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["rule"] == bi_alert_rule_a
    assert "recent_notifications" in resp.context

    # Alias check
    alias_url = reverse("bi:alert_rule_detail", kwargs={"pk": bi_alert_rule_a.pk})
    resp_alias = client_a.get(alias_url)
    assert resp_alias.status_code == 200


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_detail_none_safe(
    client_a, tenant_a
):
    """Test detail view renders safely when created_by=None and kpi_definition=None."""
    rule = _alertssubscriptions_create_alert_rule(
        tenant_a,
        user=None,
        name="No Author Alert Rule",
        kpi_definition=None,
    )
    url = reverse("bi:bi_alert_rule_detail", kwargs={"pk": rule.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "System" in resp.content.decode()


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_edit_get(
    client_a, bi_alert_rule_a
):
    """Test edit view GET returns 200 with pre-populated form."""
    url = reverse("bi:bi_alert_rule_edit", kwargs={"pk": bi_alert_rule_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["rule"] == bi_alert_rule_a
    assert "users" in resp.context

    # Alias check
    alias_url = reverse("bi:alert_rule_edit", kwargs={"pk": bi_alert_rule_a.pk})
    resp_alias = client_a.get(alias_url)
    assert resp_alias.status_code == 200


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_edit_post_valid(
    client_a, tenant_a, bi_alert_rule_a
):
    """Test edit view POST valid data updates rule, logs audit, and redirects."""
    url = reverse("bi:bi_alert_rule_edit", kwargs={"pk": bi_alert_rule_a.pk})
    payload = _alertssubscriptions_valid_alert_rule_data(
        name="Updated Margin Alert Name",
        severity="warning",
        status="paused",
    )
    resp = client_a.post(url, data=payload)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:bi_alert_rule_detail", kwargs={"pk": bi_alert_rule_a.pk})

    bi_alert_rule_a.refresh_from_db()
    assert bi_alert_rule_a.name == "Updated Margin Alert Name"
    assert bi_alert_rule_a.severity == "warning"
    assert bi_alert_rule_a.status == "paused"

    # Audit log
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(bi_alert_rule_a.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_edit_post_invalid(
    client_a, bi_alert_rule_a
):
    """Test edit view POST with invalid data re-renders form with errors."""
    url = reverse("bi:bi_alert_rule_edit", kwargs={"pk": bi_alert_rule_a.pk})
    resp = client_a.post(url, data={"name": ""})

    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_delete_post_success(
    client_a, tenant_a, admin_user
):
    """Test delete view POST deletes rule, logs audit, and redirects to list."""
    rule = _alertssubscriptions_create_alert_rule(
        tenant_a, user=admin_user, name="To Delete Alert Rule"
    )
    url = reverse("bi:bi_alert_rule_delete", kwargs={"pk": rule.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:bi_alert_rule_list")
    assert not BiAlertRule.objects.filter(pk=rule.pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(rule.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_delete_get_rejected(
    client_a, bi_alert_rule_a
):
    """Test delete view GET returns 405 Method Not Allowed due to require_POST."""
    url = reverse("bi:bi_alert_rule_delete", kwargs={"pk": bi_alert_rule_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert BiAlertRule.objects.filter(pk=bi_alert_rule_a.pk).exists()


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_delete_non_admin_forbidden(
    member_client, bi_alert_rule_a
):
    """Test delete view returns 403 Forbidden for non-admin tenant members."""
    url = reverse("bi:bi_alert_rule_delete", kwargs={"pk": bi_alert_rule_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert BiAlertRule.objects.filter(pk=bi_alert_rule_a.pk).exists()


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_test_evaluate_tripped(
    client_a, tenant_a, admin_user
):
    """Test evaluating alert rule condition when simulated value trips threshold."""
    rule = _alertssubscriptions_create_alert_rule(
        tenant_a,
        user=admin_user,
        name="Trippable Alert Rule",
        condition_operator="gt",
        threshold_value=Decimal("100.0000"),
        status="active",
        trigger_count=0,
    )
    url = reverse("bi:bi_alert_rule_test_evaluate", kwargs={"pk": rule.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:bi_alert_rule_detail", kwargs={"pk": rule.pk})

    rule.refresh_from_db()
    assert rule.status == "tripped"
    assert rule.trigger_count == 1
    assert rule.last_triggered_at is not None
    assert rule.last_evaluated_at is not None
    assert rule.last_trigger_value == Decimal("105.2500")

    # Verify message warning
    messages = list(get_messages(resp.wsgi_request))
    assert any("CONDITION TRIPPED" in m.message for m in messages)


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_test_evaluate_normal(
    client_a, tenant_a, admin_user
):
    """Test evaluating alert rule condition when simulated value stays within bounds."""
    # When condition_operator is "lt" with threshold 10, simulated_value 15.25 is NOT < 10 -> not tripped
    rule = _alertssubscriptions_create_alert_rule(
        tenant_a,
        user=admin_user,
        name="Normal Bounds Alert Rule",
        condition_operator="lt",
        threshold_value=Decimal("10.0000"),
        status="tripped",
    )
    alias_url = reverse("bi:alert_rule_test_evaluate", kwargs={"pk": rule.pk})
    resp = client_a.post(alias_url)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:bi_alert_rule_detail", kwargs={"pk": rule.pk})

    rule.refresh_from_db()
    assert rule.status == "active"
    assert rule.last_evaluated_at is not None

    messages = list(get_messages(resp.wsgi_request))
    assert any("within normal bounds" in m.message for m in messages)


@pytest.mark.django_db
def test_alertssubscriptions_views_alert_rule_test_evaluate_get_rejected(
    client_a, bi_alert_rule_a
):
    """Test evaluation view GET returns 405 Method Not Allowed."""
    url = reverse("bi:bi_alert_rule_test_evaluate", kwargs={"pk": bi_alert_rule_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


# ==============================================================================
# 2. ReportSubscription View Tests
# ==============================================================================


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_list_get_and_stats(
    client_a, report_subscription_a, report_subscription_b
):
    """Test report subscription list view returns 200, context statistics, and filters by tenant."""
    url = reverse("bi:report_subscription_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "subscriptions" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["active_count"] >= 1
    assert "pdf_count" in resp.context
    assert "excel_count" in resp.context
    assert "status_choices" in resp.context
    assert "target_asset_type_choices" in resp.context
    assert "cadence_choices" in resp.context
    assert "export_format_choices" in resp.context

    # Verify tenant isolation
    item_pks = [s.pk for s in resp.context["subscriptions"]]
    assert report_subscription_a.pk in item_pks
    assert report_subscription_b.pk not in item_pks


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_list_search(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test searching subscriptions by name, number, external emails, or dashboard title."""
    sub = _alertssubscriptions_create_subscription(
        tenant_a,
        dashboard=bi_dashboard_a,
        user=admin_user,
        name="ExecutiveStrategicDigestAlpha",
        external_recipient_emails="chief-strategy@acme.com",
    )
    url = reverse("bi:report_subscription_list")

    # Search by name
    resp_name = client_a.get(url, {"q": "StrategicDigest"})
    assert resp_name.status_code == 200
    assert any(s.pk == sub.pk for s in resp_name.context["subscriptions"])

    # Search by email
    resp_email = client_a.get(url, {"q": "chief-strategy"})
    assert resp_email.status_code == 200
    assert any(s.pk == sub.pk for s in resp_email.context["subscriptions"])

    # Negative search
    resp_neg = client_a.get(url, {"q": "NonExistentZetaSubscription999"})
    assert resp_neg.status_code == 200
    assert not any(s.pk == sub.pk for s in resp_neg.context["subscriptions"])


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_list_filters(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test filtering subscriptions by target_asset_type, cadence, format, and status."""
    sub = _alertssubscriptions_create_subscription(
        tenant_a,
        dashboard=bi_dashboard_a,
        user=admin_user,
        name="Monthly Excel Subscription",
        cadence="monthly",
        export_format="xlsx",
        status="paused",
    )
    url = reverse("bi:report_subscription_list")

    # Filter by cadence
    resp_cadence = client_a.get(url, {"cadence": "monthly"})
    assert resp_cadence.status_code == 200
    assert all(s.cadence == "monthly" for s in resp_cadence.context["subscriptions"])

    # Filter by format
    resp_fmt = client_a.get(url, {"format": "xlsx"})
    assert resp_fmt.status_code == 200
    assert all(s.export_format == "xlsx" for s in resp_fmt.context["subscriptions"])

    # Filter by status
    resp_status = client_a.get(url, {"status": "paused"})
    assert resp_status.status_code == 200
    assert all(s.status == "paused" for s in resp_status.context["subscriptions"])


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_list_pagination(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test pagination splits items into pages (page size 15)."""
    bulk = [
        ReportSubscription(
            tenant=tenant_a,
            number=f"BSUB-PAG-{i:05d}",
            name=f"Paginated Sub {i}",
            target_asset_type="dashboard",
            dashboard=bi_dashboard_a,
            cadence="weekly",
            export_format="pdf",
            burst_mode="broadcast",
            status="active",
            created_by=admin_user,
        )
        for i in range(16)
    ]
    ReportSubscription.objects.bulk_create(bulk)

    url = reverse("bi:report_subscription_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["subscriptions"]) == 15

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["subscriptions"]) >= 1


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_list_empty(client_a, tenant_a):
    """Test empty state when tenant has no subscriptions."""
    ReportSubscription.objects.filter(tenant=tenant_a).delete()
    url = reverse("bi:report_subscription_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["total_count"] == 0
    assert len(resp.context["subscriptions"]) == 0


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_create_get(client_a):
    """Test subscription create view GET returns 200 with form and foreign choices."""
    url = reverse("bi:report_subscription_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["subscription"] is None
    assert "dashboards" in resp.context
    assert "reports" in resp.context
    assert "org_units" in resp.context
    assert "users" in resp.context


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_create_post_valid(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test subscription create view POST creates record, logs audit, and redirects."""
    url = reverse("bi:report_subscription_create")
    payload = _alertssubscriptions_valid_subscription_data(
        name="POST Created Subscription",
        dashboard=bi_dashboard_a,
        subscriber_users=[admin_user],
    )
    resp = client_a.post(url, data=payload)

    assert resp.status_code == 302
    created = ReportSubscription.objects.filter(name="POST Created Subscription", tenant=tenant_a).first()
    assert created is not None
    assert created.created_by == admin_user
    assert resp.url == reverse("bi:report_subscription_detail", kwargs={"pk": created.pk})

    # Audit log check
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_create_post_invalid(client_a):
    """Test subscription create view POST invalid data re-renders form with errors."""
    url = reverse("bi:report_subscription_create")
    resp = client_a.post(url, data={})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_detail_get(
    client_a, report_subscription_a
):
    """Test subscription detail view returns 200 with subscription and recent burst runs."""
    url = reverse("bi:report_subscription_detail", kwargs={"pk": report_subscription_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["subscription"] == report_subscription_a
    assert "recent_burst_runs" in resp.context


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_detail_none_safe(
    client_a, tenant_a
):
    """Test subscription detail view renders safely when created_by=None and dashboard=None."""
    sub = _alertssubscriptions_create_subscription(
        tenant_a,
        user=None,
        name="No Creator Subscription",
        dashboard=None,
        report=None,
    )
    url = reverse("bi:report_subscription_detail", kwargs={"pk": sub.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "System" in resp.content.decode()


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_edit_get(
    client_a, report_subscription_a
):
    """Test subscription edit view GET returns 200 with populated form."""
    url = reverse("bi:report_subscription_edit", kwargs={"pk": report_subscription_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["subscription"] == report_subscription_a
    assert "users" in resp.context


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_edit_post_valid(
    client_a, tenant_a, report_subscription_a, bi_dashboard_a
):
    """Test subscription edit view POST updates record, logs audit, and redirects."""
    url = reverse("bi:report_subscription_edit", kwargs={"pk": report_subscription_a.pk})
    payload = _alertssubscriptions_valid_subscription_data(
        name="Updated Subscription Title",
        dashboard=bi_dashboard_a,
        cadence="monthly",
        status="paused",
    )
    resp = client_a.post(url, data=payload)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_subscription_detail", kwargs={"pk": report_subscription_a.pk})

    report_subscription_a.refresh_from_db()
    assert report_subscription_a.name == "Updated Subscription Title"
    assert report_subscription_a.cadence == "monthly"
    assert report_subscription_a.status == "paused"

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(report_subscription_a.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_edit_post_invalid(
    client_a, report_subscription_a
):
    """Test subscription edit view POST invalid data re-renders form with errors."""
    url = reverse("bi:report_subscription_edit", kwargs={"pk": report_subscription_a.pk})
    resp = client_a.post(url, data={"name": ""})

    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_delete_post_success(
    client_a, tenant_a, admin_user
):
    """Test subscription delete view POST deletes record, logs audit, and redirects."""
    sub = _alertssubscriptions_create_subscription(
        tenant_a, user=admin_user, name="To Delete Subscription"
    )
    url = reverse("bi:report_subscription_delete", kwargs={"pk": sub.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_subscription_list")
    assert not ReportSubscription.objects.filter(pk=sub.pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(sub.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_delete_get_rejected(
    client_a, report_subscription_a
):
    """Test subscription delete view GET returns 405 Method Not Allowed."""
    url = reverse("bi:report_subscription_delete", kwargs={"pk": report_subscription_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert ReportSubscription.objects.filter(pk=report_subscription_a.pk).exists()


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_delete_non_admin_forbidden(
    member_client, report_subscription_a
):
    """Test subscription delete view returns 403 Forbidden for non-admin tenant members."""
    url = reverse("bi:report_subscription_delete", kwargs={"pk": report_subscription_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert ReportSubscription.objects.filter(pk=report_subscription_a.pk).exists()


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_run_now(
    client_a, tenant_a, admin_user, report_subscription_a
):
    """Test trigger immediate run generates DistributionBurstRun, increments run stats, and redirects."""
    initial_run_count = report_subscription_a.run_count
    url = reverse("bi:report_subscription_run_now", kwargs={"pk": report_subscription_a.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    burst_run = DistributionBurstRun.objects.filter(
        subscription=report_subscription_a,
        tenant=tenant_a,
        run_trigger="ad_hoc_manual",
    ).first()
    assert burst_run is not None
    assert burst_run.status == "completed"
    assert burst_run.executed_by == admin_user
    assert resp.url == reverse("bi:distribution_burst_run_detail", kwargs={"pk": burst_run.pk})

    report_subscription_a.refresh_from_db()
    assert report_subscription_a.run_count == initial_run_count + 1
    assert report_subscription_a.last_run_at is not None

    # Audit log check
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(burst_run.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_report_subscription_run_now_get_rejected(
    client_a, report_subscription_a
):
    """Test immediate run view GET returns 405 Method Not Allowed."""
    url = reverse("bi:report_subscription_run_now", kwargs={"pk": report_subscription_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


# ==============================================================================
# 3. DistributionBurstRun View Tests
# ==============================================================================


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_list_get_and_stats(
    client_a, distribution_burst_run_a, distribution_burst_run_b
):
    """Test burst run list view returns 200, context statistics, and filters by tenant."""
    url = reverse("bi:distribution_burst_run_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "burst_runs" in resp.context
    assert resp.context["total_runs"] >= 1
    assert resp.context["completed_runs"] >= 1
    assert "failed_runs" in resp.context
    assert "total_delivered_recipients" in resp.context
    assert "run_trigger_choices" in resp.context
    assert "delivery_channel_choices" in resp.context
    assert "status_choices" in resp.context

    # Tenant scoping check
    item_pks = [b.pk for b in resp.context["burst_runs"]]
    assert distribution_burst_run_a.pk in item_pks
    assert distribution_burst_run_b.pk not in item_pks


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_list_search(
    client_a, tenant_a, admin_user, report_subscription_a
):
    """Test searching burst runs by number, generated file name, or error summary."""
    run = _alertssubscriptions_create_burst_run(
        tenant_a,
        subscription=report_subscription_a,
        user=admin_user,
        generated_file_name="UniqueBurstReport20261108.pdf",
        error_summary="SpecificNetworkFailureDiagnosticsAlpha",
    )
    url = reverse("bi:distribution_burst_run_list")

    # Search by generated file name
    resp_file = client_a.get(url, {"q": "UniqueBurstReport"})
    assert resp_file.status_code == 200
    assert any(b.pk == run.pk for b in resp_file.context["burst_runs"])

    # Search by error summary
    resp_err = client_a.get(url, {"q": "SpecificNetworkFailure"})
    assert resp_err.status_code == 200
    assert any(b.pk == run.pk for b in resp_err.context["burst_runs"])

    # Negative search
    resp_neg = client_a.get(url, {"q": "NonExistentZetaBurst999"})
    assert resp_neg.status_code == 200
    assert not any(b.pk == run.pk for b in resp_neg.context["burst_runs"])


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_list_filters(
    client_a, tenant_a, admin_user, report_subscription_a
):
    """Test filtering burst runs by trigger, channel, and status."""
    run = _alertssubscriptions_create_burst_run(
        tenant_a,
        subscription=report_subscription_a,
        user=admin_user,
        run_trigger="ad_hoc_manual",
        delivery_channel="webhook",
        status="partial_failure",
    )
    url = reverse("bi:distribution_burst_run_list")

    # Filter by trigger
    resp_trig = client_a.get(url, {"trigger": "ad_hoc_manual"})
    assert resp_trig.status_code == 200
    assert all(b.run_trigger == "ad_hoc_manual" for b in resp_trig.context["burst_runs"])

    # Filter by channel
    resp_chan = client_a.get(url, {"channel": "webhook"})
    assert resp_chan.status_code == 200
    assert all(b.delivery_channel == "webhook" for b in resp_chan.context["burst_runs"])

    # Filter by status
    resp_stat = client_a.get(url, {"status": "partial_failure"})
    assert resp_stat.status_code == 200
    assert all(b.status == "partial_failure" for b in resp_stat.context["burst_runs"])


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_list_pagination(
    client_a, tenant_a, admin_user, report_subscription_a
):
    """Test burst run list pagination at page size 15."""
    bulk = [
        DistributionBurstRun(
            tenant=tenant_a,
            number=f"BBRS-PAG-{i:05d}",
            subscription=report_subscription_a,
            run_trigger="scheduled_subscription",
            delivery_channel="email",
            status="completed",
            recipient_count=1,
            delivered_count=1,
            executed_by=admin_user,
        )
        for i in range(16)
    ]
    DistributionBurstRun.objects.bulk_create(bulk)

    url = reverse("bi:distribution_burst_run_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["burst_runs"]) == 15

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["burst_runs"]) >= 1


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_list_empty(client_a, tenant_a):
    """Test empty state when tenant has no burst runs."""
    DistributionBurstRun.objects.filter(tenant=tenant_a).delete()
    url = reverse("bi:distribution_burst_run_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["total_runs"] == 0
    assert len(resp.context["burst_runs"]) == 0


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_create_get(client_a):
    """Test burst run create view GET returns 200 with form and choices."""
    url = reverse("bi:distribution_burst_run_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["burst_run"] is None
    assert "subscriptions" in resp.context
    assert "rules" in resp.context


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_create_post_valid(
    client_a, tenant_a, admin_user, report_subscription_a
):
    """Test burst run create view POST valid data creates record, logs audit, and redirects."""
    url = reverse("bi:distribution_burst_run_create")
    payload = _alertssubscriptions_valid_burst_run_data(
        subscription=report_subscription_a,
        recipient_count=8,
        generated_file_name="AdHocBatch_20261108.pdf",
    )
    resp = client_a.post(url, data=payload)

    assert resp.status_code == 302
    created = DistributionBurstRun.objects.filter(
        generated_file_name="AdHocBatch_20261108.pdf", tenant=tenant_a
    ).first()
    assert created is not None
    assert created.executed_by == admin_user
    assert created.delivered_count == 8
    assert resp.url == reverse("bi:distribution_burst_run_detail", kwargs={"pk": created.pk})

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_create_post_invalid(client_a):
    """Test burst run create view POST invalid data re-renders form with errors."""
    url = reverse("bi:distribution_burst_run_create")
    resp = client_a.post(url, data={"recipient_count": -5})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_detail_get(
    client_a, distribution_burst_run_a
):
    """Test burst run detail view returns 200 with burst_run and notifications context."""
    url = reverse("bi:distribution_burst_run_detail", kwargs={"pk": distribution_burst_run_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["burst_run"] == distribution_burst_run_a
    assert "notifications" in resp.context


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_detail_none_safe(client_a, tenant_a):
    """Test burst run detail view renders safely when executed_by=None and subscription=None."""
    run = _alertssubscriptions_create_burst_run(
        tenant_a,
        user=None,
        subscription=None,
        alert_rule=None,
    )
    url = reverse("bi:distribution_burst_run_detail", kwargs={"pk": run.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "Ad-Hoc Manual Dispatch" in resp.content.decode()


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_edit_get(
    client_a, distribution_burst_run_a
):
    """Test burst run edit view GET returns 200 with pre-populated form."""
    url = reverse("bi:distribution_burst_run_edit", kwargs={"pk": distribution_burst_run_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["burst_run"] == distribution_burst_run_a


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_edit_post_valid(
    client_a, tenant_a, distribution_burst_run_a
):
    """Test burst run edit view POST updates record, logs audit, and redirects."""
    url = reverse("bi:distribution_burst_run_edit", kwargs={"pk": distribution_burst_run_a.pk})
    payload = _alertssubscriptions_valid_burst_run_data(
        status="failed",
        error_summary="Updated SMTP Connection Timeout.",
    )
    resp = client_a.post(url, data=payload)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:distribution_burst_run_detail", kwargs={"pk": distribution_burst_run_a.pk})

    distribution_burst_run_a.refresh_from_db()
    assert distribution_burst_run_a.status == "failed"
    assert "SMTP Connection Timeout" in distribution_burst_run_a.error_summary

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(distribution_burst_run_a.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_edit_post_invalid(
    client_a, distribution_burst_run_a
):
    """Test burst run edit view POST invalid data re-renders form with errors."""
    url = reverse("bi:distribution_burst_run_edit", kwargs={"pk": distribution_burst_run_a.pk})
    resp = client_a.post(url, data={"recipient_count": -10})

    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_delete_post_success(
    client_a, tenant_a, admin_user
):
    """Test burst run delete view POST deletes record, logs audit, and redirects."""
    run = _alertssubscriptions_create_burst_run(
        tenant_a, user=admin_user
    )
    url = reverse("bi:distribution_burst_run_delete", kwargs={"pk": run.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:distribution_burst_run_list")
    assert not DistributionBurstRun.objects.filter(pk=run.pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(run.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_delete_get_rejected(
    client_a, distribution_burst_run_a
):
    """Test burst run delete view GET returns 405 Method Not Allowed."""
    url = reverse("bi:distribution_burst_run_delete", kwargs={"pk": distribution_burst_run_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert DistributionBurstRun.objects.filter(pk=distribution_burst_run_a.pk).exists()


@pytest.mark.django_db
def test_alertssubscriptions_views_burst_run_delete_non_admin_forbidden(
    member_client, distribution_burst_run_a
):
    """Test burst run delete view returns 403 Forbidden for non-admin tenant members."""
    url = reverse("bi:distribution_burst_run_delete", kwargs={"pk": distribution_burst_run_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert DistributionBurstRun.objects.filter(pk=distribution_burst_run_a.pk).exists()


# ==============================================================================
# 4. BiNotificationItem View Tests & Notification Center Workspace
# ==============================================================================


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_list_get_and_stats(
    client_a, bi_notification_item_a, bi_notification_item_b
):
    """Test notification list view returns 200, context statistics, and filters by tenant."""
    url = reverse("bi:bi_notification_item_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "notifications" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["unread_count"] >= 1
    assert "critical_count" in resp.context
    assert "escalated_count" in resp.context
    assert "severity_choices" in resp.context
    assert "category_choices" in resp.context
    assert "status_choices" in resp.context

    # Tenant scoping check
    item_pks = [n.pk for n in resp.context["notifications"]]
    assert bi_notification_item_a.pk in item_pks
    assert bi_notification_item_b.pk not in item_pks

    # Alias check
    alias_url = reverse("bi:notification_item_list")
    resp_alias = client_a.get(alias_url)
    assert resp_alias.status_code == 200


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_list_search(
    client_a, tenant_a, admin_user
):
    """Test searching notifications by title, number, or message."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a,
        recipient=admin_user,
        title="UniqueNotificationSubjectAlpha",
        message="Critical operational threshold exceeded on main data lake",
    )
    url = reverse("bi:bi_notification_item_list")

    # Search by title
    resp_title = client_a.get(url, {"q": "SubjectAlpha"})
    assert resp_title.status_code == 200
    assert any(n.pk == item.pk for n in resp_title.context["notifications"])

    # Search by message
    resp_msg = client_a.get(url, {"q": "data lake"})
    assert resp_msg.status_code == 200
    assert any(n.pk == item.pk for n in resp_msg.context["notifications"])

    # Negative search
    resp_neg = client_a.get(url, {"q": "NonExistentZetaNotification999"})
    assert resp_neg.status_code == 200
    assert not any(n.pk == item.pk for n in resp_neg.context["notifications"])


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_list_filters(
    client_a, tenant_a, admin_user
):
    """Test filtering notifications by severity, category, and status."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a,
        recipient=admin_user,
        title="Escalated Anomaly Notice",
        severity="critical",
        category="anomaly_alert",
        status="escalated",
    )
    url = reverse("bi:bi_notification_item_list")

    # Filter by severity
    resp_sev = client_a.get(url, {"severity": "critical"})
    assert resp_sev.status_code == 200
    assert all(n.severity == "critical" for n in resp_sev.context["notifications"])

    # Filter by category
    resp_cat = client_a.get(url, {"category": "anomaly_alert"})
    assert resp_cat.status_code == 200
    assert all(n.category == "anomaly_alert" for n in resp_cat.context["notifications"])

    # Filter by status
    resp_stat = client_a.get(url, {"status": "escalated"})
    assert resp_stat.status_code == 200
    assert all(n.status == "escalated" for n in resp_stat.context["notifications"])


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test notification list pagination at page size 15."""
    bulk = [
        BiNotificationItem(
            tenant=tenant_a,
            number=f"BNTF-PAG-{i:05d}",
            recipient=admin_user,
            title=f"Paginated Notice {i}",
            message="Message content",
            severity="info",
            category="kpi_alert",
            status="unread",
        )
        for i in range(16)
    ]
    BiNotificationItem.objects.bulk_create(bulk)

    url = reverse("bi:bi_notification_item_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["notifications"]) == 15

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["notifications"]) >= 1


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_list_empty(client_a, tenant_a):
    """Test empty state when tenant has no notifications."""
    BiNotificationItem.objects.filter(tenant=tenant_a).delete()
    url = reverse("bi:bi_notification_item_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["total_count"] == 0
    assert len(resp.context["notifications"]) == 0


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_create_get(client_a):
    """Test notification create view GET returns 200 with form and foreign choices."""
    url = reverse("bi:bi_notification_item_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["notification"] is None
    assert "users" in resp.context
    assert "rules" in resp.context
    assert "burst_runs" in resp.context

    # Alias check
    alias_url = reverse("bi:notification_item_create")
    resp_alias = client_a.get(alias_url)
    assert resp_alias.status_code == 200


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_create_post_valid(
    client_a, tenant_a, admin_user, bi_alert_rule_a
):
    """Test notification create view POST creates record, logs audit, and redirects."""
    url = reverse("bi:bi_notification_item_create")
    payload = _alertssubscriptions_valid_notification_data(
        recipient=admin_user,
        alert_rule=bi_alert_rule_a,
        title="Created Notification Notice",
    )
    resp = client_a.post(url, data=payload)

    assert resp.status_code == 302
    created = BiNotificationItem.objects.filter(
        title="Created Notification Notice", tenant=tenant_a
    ).first()
    assert created is not None
    assert resp.url == reverse("bi:bi_notification_item_detail", kwargs={"pk": created.pk})

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_create_post_valid_alias(
    client_a, tenant_a, admin_user
):
    """Test notification create view alias notification_item_create POST functions identically."""
    alias_url = reverse("bi:notification_item_create")
    payload = _alertssubscriptions_valid_notification_data(
        recipient=admin_user,
        title="Created Via Alias Notification",
    )
    resp = client_a.post(alias_url, data=payload)
    assert resp.status_code == 302
    created = BiNotificationItem.objects.filter(
        title="Created Via Alias Notification", tenant=tenant_a
    ).first()
    assert created is not None
    assert resp.url == reverse("bi:bi_notification_item_detail", kwargs={"pk": created.pk})


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_create_post_invalid(client_a):
    """Test notification create view POST invalid data re-renders form with errors."""
    url = reverse("bi:bi_notification_item_create")
    resp = client_a.post(url, data={})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_detail_auto_mark_read(
    client_a, tenant_a, admin_user
):
    """Test detail view automatically marks unread notification as read when viewed by recipient."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a,
        recipient=admin_user,
        status="unread",
    )
    assert item.read_at is None

    url = reverse("bi:bi_notification_item_detail", kwargs={"pk": item.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["notification"] == item

    item.refresh_from_db()
    assert item.status == "read"
    assert item.read_at is not None

    # Alias check
    alias_url = reverse("bi:notification_item_detail", kwargs={"pk": item.pk})
    resp_alias = client_a.get(alias_url)
    assert resp_alias.status_code == 200


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_detail_other_recipient_no_mark_read(
    client_a, tenant_a, member_user
):
    """Test detail view does NOT mark as read when viewed by non-recipient user."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a,
        recipient=member_user,
        status="unread",
    )
    url = reverse("bi:bi_notification_item_detail", kwargs={"pk": item.pk})
    resp = client_a.get(url)  # viewed by admin_user, not member_user

    assert resp.status_code == 200
    item.refresh_from_db()
    assert item.status == "unread"
    assert item.read_at is None


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_edit_get(
    client_a, bi_notification_item_a
):
    """Test notification edit view GET returns 200 with populated form."""
    url = reverse("bi:bi_notification_item_edit", kwargs={"pk": bi_notification_item_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["notification"] == bi_notification_item_a
    assert "users" in resp.context

    # Alias check
    alias_url = reverse("bi:notification_item_edit", kwargs={"pk": bi_notification_item_a.pk})
    resp_alias = client_a.get(alias_url)
    assert resp_alias.status_code == 200


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_edit_post_valid(
    client_a, tenant_a, admin_user, bi_notification_item_a
):
    """Test notification edit view POST updates record, logs audit, and redirects."""
    url = reverse("bi:bi_notification_item_edit", kwargs={"pk": bi_notification_item_a.pk})
    payload = _alertssubscriptions_valid_notification_data(
        recipient=admin_user,
        title="Updated Notification Title Alpha",
        severity="warning",
        status="acknowledged",
    )
    resp = client_a.post(url, data=payload)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:bi_notification_item_detail", kwargs={"pk": bi_notification_item_a.pk})

    bi_notification_item_a.refresh_from_db()
    assert bi_notification_item_a.title == "Updated Notification Title Alpha"
    assert bi_notification_item_a.severity == "warning"
    assert bi_notification_item_a.status == "acknowledged"

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(bi_notification_item_a.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_edit_post_invalid(
    client_a, bi_notification_item_a
):
    """Test notification edit view POST invalid data re-renders form with errors."""
    url = reverse("bi:bi_notification_item_edit", kwargs={"pk": bi_notification_item_a.pk})
    resp = client_a.post(url, data={"title": ""})

    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_delete_post_success(
    client_a, tenant_a, admin_user
):
    """Test notification delete view POST deletes record, logs audit, and redirects."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user
    )
    url = reverse("bi:bi_notification_item_delete", kwargs={"pk": item.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:bi_notification_item_list")
    assert not BiNotificationItem.objects.filter(pk=item.pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(item.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_delete_get_rejected(
    client_a, bi_notification_item_a
):
    """Test notification delete view GET returns 405 Method Not Allowed."""
    url = reverse("bi:bi_notification_item_delete", kwargs={"pk": bi_notification_item_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert BiNotificationItem.objects.filter(pk=bi_notification_item_a.pk).exists()


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_center_tabs(
    client_a, tenant_a, admin_user
):
    """Test notification center workspace returns 200 and correctly filters by tab."""
    # Seed various items for the user
    item_unread = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, status="unread", severity="info"
    )
    item_crit = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, status="unread", severity="critical"
    )
    item_snoozed = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, status="snoozed", severity="info"
    )
    item_escalated = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, status="escalated", severity="warning"
    )

    url = reverse("bi:notification_center")

    # Tab "all"
    resp_all = client_a.get(url, {"tab": "all"})
    assert resp_all.status_code == 200
    assert "inbox_items" in resp_all.context
    assert resp_all.context["unread_count"] >= 1
    assert resp_all.context["critical_count"] >= 1
    assert resp_all.context["snoozed_count"] >= 1
    assert resp_all.context["escalated_count"] >= 1
    assert resp_all.context["active_tab"] == "all"

    # Tab "unread"
    resp_unread = client_a.get(url, {"tab": "unread"})
    assert resp_unread.status_code == 200
    assert all(n.status == "unread" for n in resp_unread.context["inbox_items"])

    # Tab "critical"
    resp_critical = client_a.get(url, {"tab": "critical"})
    assert resp_critical.status_code == 200
    assert all(n.severity == "critical" for n in resp_critical.context["inbox_items"])

    # Tab "snoozed"
    resp_snoozed = client_a.get(url, {"tab": "snoozed"})
    assert resp_snoozed.status_code == 200
    assert all(n.status == "snoozed" for n in resp_snoozed.context["inbox_items"])

    # Tab "escalated"
    resp_escalated = client_a.get(url, {"tab": "escalated"})
    assert resp_escalated.status_code == 200
    assert all(n.status == "escalated" for n in resp_escalated.context["inbox_items"])


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_center_category_filter(
    client_a, tenant_a, admin_user
):
    """Test notification center filtering by category."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, category="workflow_task"
    )
    url = reverse("bi:notification_center")
    resp = client_a.get(url, {"category": "workflow_task"})

    assert resp.status_code == 200
    assert all(n.category == "workflow_task" for n in resp.context["inbox_items"])


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_center_user_scoping(
    client_a, tenant_a, admin_user, member_user
):
    """Test notification center inbox includes only items assigned to request.user or unassigned."""
    item_admin = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, title="Admin Exclusive Notice"
    )
    item_member = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=member_user, title="Member Exclusive Notice"
    )
    url = reverse("bi:notification_center")
    resp = client_a.get(url)

    assert resp.status_code == 200
    inbox_pks = [n.pk for n in resp.context["inbox_items"]]
    assert item_admin.pk in inbox_pks
    assert item_member.pk not in inbox_pks


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_mark_read(
    client_a, tenant_a, admin_user
):
    """Test notification_mark_read POST marks notification as read with timestamp and redirects."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, status="unread"
    )
    url = reverse("bi:notification_mark_read", kwargs={"pk": item.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:notification_center")

    item.refresh_from_db()
    assert item.status == "read"
    assert item.read_at is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_mark_read_get_rejected(
    client_a, bi_notification_item_a
):
    """Test mark_read view GET returns 405 Method Not Allowed."""
    url = reverse("bi:notification_mark_read", kwargs={"pk": bi_notification_item_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_acknowledge(
    client_a, tenant_a, admin_user
):
    """Test notification_acknowledge POST marks acknowledged, stores notes, logs audit, and redirects."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, status="unread"
    )
    url = reverse("bi:notification_acknowledge", kwargs={"pk": item.pk})
    resp = client_a.post(url, data={"notes": "Resolved during operational incident triage"})

    assert resp.status_code == 302
    assert resp.url == reverse("bi:notification_center")

    item.refresh_from_db()
    assert item.status == "acknowledged"
    assert item.acknowledged_at is not None
    assert item.acknowledged_by == admin_user
    assert item.acknowledgment_notes == "Resolved during operational incident triage"

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(item.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_acknowledge_get_rejected(
    client_a, bi_notification_item_a
):
    """Test acknowledge view GET returns 405 Method Not Allowed."""
    url = reverse("bi:notification_acknowledge", kwargs={"pk": bi_notification_item_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_snooze_valid_and_invalid_hours(
    client_a, tenant_a, admin_user
):
    """Test notification_snooze POST updates status to snoozed and validates allowed hours."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, status="unread"
    )
    url = reverse("bi:notification_snooze", kwargs={"pk": item.pk})

    # Test valid 24 hours
    now = timezone.now()
    resp_24 = client_a.post(url, data={"hours": "24"})
    assert resp_24.status_code == 302
    item.refresh_from_db()
    assert item.status == "snoozed"
    assert item.snoozed_until > now + timedelta(hours=23)

    # Test invalid string hours (should fallback gracefully to 4 hours)
    resp_invalid = client_a.post(url, data={"hours": "invalid_string_999"})
    assert resp_invalid.status_code == 302
    item.refresh_from_db()
    assert item.status == "snoozed"
    assert item.snoozed_until > now + timedelta(hours=3)

    # Verify audit log
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(item.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_snooze_get_rejected(
    client_a, bi_notification_item_a
):
    """Test snooze view GET returns 405 Method Not Allowed."""
    url = reverse("bi:notification_snooze", kwargs={"pk": bi_notification_item_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_escalate(
    client_a, tenant_a, admin_user
):
    """Test notification_escalate POST increments level, clamps at 3, logs audit, and redirects."""
    item = _alertssubscriptions_create_notification_item(
        tenant_a, recipient=admin_user, status="unread", escalation_level=0
    )
    url = reverse("bi:notification_escalate", kwargs={"pk": item.pk})

    # Escalate from level 0 -> 1
    resp1 = client_a.post(url)
    assert resp1.status_code == 302
    item.refresh_from_db()
    assert item.status == "escalated"
    assert item.escalation_level == 1

    # Escalate 1 -> 2
    client_a.post(url)
    item.refresh_from_db()
    assert item.escalation_level == 2

    # Escalate 2 -> 3
    client_a.post(url)
    item.refresh_from_db()
    assert item.escalation_level == 3

    # Clamping test: escalate at 3 remains 3
    client_a.post(url)
    item.refresh_from_db()
    assert item.escalation_level == 3

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(item.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_alertssubscriptions_views_notification_escalate_get_rejected(
    client_a, bi_notification_item_a
):
    """Test escalate view GET returns 405 Method Not Allowed."""
    url = reverse("bi:notification_escalate", kwargs={"pk": bi_notification_item_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


# ==============================================================================
# 5. Cross-Tenant Isolation & Unauthenticated Access
# ==============================================================================


@pytest.mark.django_db
def test_alertssubscriptions_views_cross_tenant_isolation(
    client_a,
    bi_alert_rule_b,
    report_subscription_b,
    distribution_burst_run_b,
    bi_notification_item_b,
):
    """Test Tenant A user cannot view, edit, evaluate, or mutate Tenant B entities (404 Http404)."""
    # Alert Rule
    assert client_a.get(reverse("bi:bi_alert_rule_detail", kwargs={"pk": bi_alert_rule_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:bi_alert_rule_edit", kwargs={"pk": bi_alert_rule_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:bi_alert_rule_delete", kwargs={"pk": bi_alert_rule_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:bi_alert_rule_test_evaluate", kwargs={"pk": bi_alert_rule_b.pk})).status_code == 404

    # Report Subscription
    assert client_a.get(reverse("bi:report_subscription_detail", kwargs={"pk": report_subscription_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:report_subscription_edit", kwargs={"pk": report_subscription_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:report_subscription_delete", kwargs={"pk": report_subscription_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:report_subscription_run_now", kwargs={"pk": report_subscription_b.pk})).status_code == 404

    # Burst Run
    assert client_a.get(reverse("bi:distribution_burst_run_detail", kwargs={"pk": distribution_burst_run_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:distribution_burst_run_edit", kwargs={"pk": distribution_burst_run_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:distribution_burst_run_delete", kwargs={"pk": distribution_burst_run_b.pk})).status_code == 404

    # Notification Item
    assert client_a.get(reverse("bi:bi_notification_item_detail", kwargs={"pk": bi_notification_item_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:bi_notification_item_edit", kwargs={"pk": bi_notification_item_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:bi_notification_item_delete", kwargs={"pk": bi_notification_item_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:notification_mark_read", kwargs={"pk": bi_notification_item_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:notification_acknowledge", kwargs={"pk": bi_notification_item_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:notification_snooze", kwargs={"pk": bi_notification_item_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:notification_escalate", kwargs={"pk": bi_notification_item_b.pk})).status_code == 404


@pytest.mark.django_db
def test_alertssubscriptions_views_unauthenticated_redirects(
    anon_client,
    bi_alert_rule_a,
    report_subscription_a,
    distribution_burst_run_a,
    bi_notification_item_a,
):
    """Test unauthenticated anonymous user is redirected (302) to login on all views."""
    # List and Workspace views
    assert anon_client.get(reverse("bi:bi_alert_rule_list")).status_code == 302
    assert anon_client.get(reverse("bi:report_subscription_list")).status_code == 302
    assert anon_client.get(reverse("bi:distribution_burst_run_list")).status_code == 302
    assert anon_client.get(reverse("bi:bi_notification_item_list")).status_code == 302
    assert anon_client.get(reverse("bi:notification_center")).status_code == 302

    # Detail views
    assert anon_client.get(reverse("bi:bi_alert_rule_detail", kwargs={"pk": bi_alert_rule_a.pk})).status_code == 302
    assert anon_client.get(reverse("bi:report_subscription_detail", kwargs={"pk": report_subscription_a.pk})).status_code == 302
    assert anon_client.get(reverse("bi:distribution_burst_run_detail", kwargs={"pk": distribution_burst_run_a.pk})).status_code == 302
    assert anon_client.get(reverse("bi:bi_notification_item_detail", kwargs={"pk": bi_notification_item_a.pk})).status_code == 302

    # Action endpoints
    assert anon_client.post(reverse("bi:bi_alert_rule_test_evaluate", kwargs={"pk": bi_alert_rule_a.pk})).status_code == 302
    assert anon_client.post(reverse("bi:report_subscription_run_now", kwargs={"pk": report_subscription_a.pk})).status_code == 302
    assert anon_client.post(reverse("bi:notification_mark_read", kwargs={"pk": bi_notification_item_a.pk})).status_code == 302
    assert anon_client.post(reverse("bi:notification_acknowledge", kwargs={"pk": bi_notification_item_a.pk})).status_code == 302
    assert anon_client.post(reverse("bi:notification_snooze", kwargs={"pk": bi_notification_item_a.pk})).status_code == 302
    assert anon_client.post(reverse("bi:notification_escalate", kwargs={"pk": bi_notification_item_a.pk})).status_code == 302
