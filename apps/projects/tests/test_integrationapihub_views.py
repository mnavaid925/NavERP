import html
import json
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.projects.models import (
    ConnectorFieldMapping,
    ProjectIntegrationConnector,
    ProjectSyncJob,
    ProjectSyncRun,
)
from apps.projects.models.IntegrationApiHub.SyncRuns import SYNC_BACKOFF_SECONDS
from apps.projects.tests.conftest import (
    INTEGRATIONAPIHUB_PAGE_SIZE,
    _integrationapihub_connector,
    _integrationapihub_job,
    _integrationapihub_mapping,
    _integrationapihub_run,
)

pytestmark = pytest.mark.django_db

_INTEGRATIONAPIHUB_ROUTES = (
    ("ixc_list", (), "/projects/integration/connectors/"),
    ("ixc_create", (), "/projects/integration/connectors/add/"),
    ("ixc_erp_list", (), "/projects/integration/connectors/erp/"),
    ("ixc_crm_list", (), "/projects/integration/connectors/crm/"),
    ("ixc_hris_list", (), "/projects/integration/connectors/hris/"),
    ("ixc_devops_list", (), "/projects/integration/connectors/devops/"),
    ("ixc_storage_list", (), "/projects/integration/connectors/storage/"),
    ("ixc_detail", (7,), "/projects/integration/connectors/7/"),
    ("ixc_edit", (7,), "/projects/integration/connectors/7/edit/"),
    ("ixc_delete", (7,), "/projects/integration/connectors/7/delete/"),
    ("ixc_rotate_credential", (7,), "/projects/integration/connectors/7/rotate-credential/"),
    ("ixc_test", (7,), "/projects/integration/connectors/7/test/"),
    ("ixc_toggle_active", (7,), "/projects/integration/connectors/7/toggle/"),
    ("connector_health", (7,), "/projects/integration/connectors/7/health/"),
    ("ixm_list", (), "/projects/integration/mappings/"),
    ("ixm_create", (), "/projects/integration/mappings/add/"),
    ("ixm_detail", (7,), "/projects/integration/mappings/7/"),
    ("ixm_edit", (7,), "/projects/integration/mappings/7/edit/"),
    ("ixm_delete", (7,), "/projects/integration/mappings/7/delete/"),
    ("syj_list", (), "/projects/integration/sync-jobs/"),
    ("syj_create", (), "/projects/integration/sync-jobs/add/"),
    ("syj_detail", (7,), "/projects/integration/sync-jobs/7/"),
    ("syj_edit", (7,), "/projects/integration/sync-jobs/7/edit/"),
    ("syj_delete", (7,), "/projects/integration/sync-jobs/7/delete/"),
    ("syj_run", (7,), "/projects/integration/sync-jobs/7/run/"),
    ("syj_toggle_active", (7,), "/projects/integration/sync-jobs/7/toggle/"),
    ("syr_list", (), "/projects/integration/runs/"),
    ("syr_detail", (7,), "/projects/integration/runs/7/"),
    ("syr_retry", (7,), "/projects/integration/runs/7/retry/"),
    ("integration_hub", (), "/projects/integration/hub/"),
    ("sync_monitor", (), "/projects/integration/monitor/"),
)

_INTEGRATIONAPIHUB_POST_ONLY = (
    ("ixc_delete", "integrationapihub_connector_a"),
    ("ixc_rotate_credential", "integrationapihub_connector_a"),
    ("ixc_test", "integrationapihub_connector_a"),
    ("ixc_toggle_active", "integrationapihub_connector_a"),
    ("ixm_delete", "integrationapihub_mapping_a"),
    ("syj_delete", "integrationapihub_job_a"),
    ("syj_run", "integrationapihub_job_a"),
    ("syj_toggle_active", "integrationapihub_job_a"),
    ("syr_retry", "integrationapihub_run_failed_a"),
)


def _integrationapihub_url(name, *args):
    return reverse(f"projects:{name}", args=args)


def _integrationapihub_get(client, name, /, *args, follow=False, **params):
    return client.get(_integrationapihub_url(name, *args), params, follow=follow)


def _integrationapihub_post(client, name, /, *args, data=None, follow=False):
    return client.post(_integrationapihub_url(name, *args), data or {}, follow=follow)


def _integrationapihub_messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def _integrationapihub_body(response):
    return html.unescape(response.content.decode())


def _integrationapihub_pks(response, key):
    return [row.pk for row in response.context[key]]


def _integrationapihub_page_query(response, page=2):
    body = _integrationapihub_body(response)
    links = re.findall(rf'href="([^"]*[?&]page={page}[^"]*)"', body)
    assert links
    query = parse_qs(urlsplit(links[0]).query)
    return {key: values[0] for key, values in query.items()}


def _integrationapihub_audits(model, object_pk, action):
    return list(
        AuditLog.objects.filter(
            content_type=ContentType.objects.get_for_model(model),
            object_id=object_pk,
            action=action,
        ).order_by("id")
    )


def _integrationapihub_measure(client, route, *args, **params):
    with CaptureQueriesContext(connection) as captured:
        response = _integrationapihub_get(client, route, *args, **params)
    assert response.status_code == 200
    return len(captured.captured_queries), response


def _integrationapihub_connector_payload(project=None, owner=None, **overrides):
    payload = {
        "project": "" if project is None else str(project.pk),
        "name": "View-created connector",
        "domain": "erp",
        "provider": "sap",
        "direction": "bidirectional",
        "auth_method": "api_key",
        "base_url": "https://configuration.example.invalid",
        "remote_scope_ref": "VIEW-01",
        "trigger_mode": "manual",
        "schedule_note": "Recorded intent only.",
        "environment": "sandbox",
        "status": "unverified",
        "is_active": "on",
        "notify_webhook": "",
        "owner": "" if owner is None else str(owner.pk),
        "notes": "No outbound request is made.",
        "credential": "",
    }
    payload.update(overrides)
    return payload


def _integrationapihub_mapping_payload(connector, **overrides):
    payload = {
        "connector": str(connector.pk),
        "local_field": "task.view_field",
        "remote_field": "fields.ViewField",
        "direction": "both",
        "transform": "none",
        "value_map": "{}",
        "default_value": "",
        "is_key": "",
        "is_required": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _integrationapihub_job_payload(connector, **overrides):
    payload = {
        "connector": str(connector.pk),
        "name": "View-created sync job",
        "entity_scope": "tasks",
        "direction": "bidirectional",
        "trigger_mode": "manual",
        "interval_minutes": "",
        "schedule_note": "",
        "filter_expression": "",
        "conflict_policy": "manual",
        "batch_size": "100",
        "is_active": "on",
    }
    payload.update(overrides)
    return payload


def test_integrationapihub_all_31_routes_reverse_to_literal_contract_paths():
    assert len(_INTEGRATIONAPIHUB_ROUTES) == 31
    for name, args, expected in _INTEGRATIONAPIHUB_ROUTES:
        assert _integrationapihub_url(name, *args) == expected


def test_integrationapihub_connector_list_renders_context_content_and_tenant_scope(
    client_a,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
    integrationapihub_project_a,
    integrationapihub_project_b,
):
    response = _integrationapihub_get(client_a, "ixc_list")
    assert response.status_code == 200
    expected = {
        "connectors", "page_obj", "projects", "domain_choices", "provider_choices",
        "status_choices", "domain", "q", "status", "provider", "project_id", "is_active", "stats",
    }
    assert expected <= set(response.context.keys())
    assert set(response.context["stats"]) == {"total", "active", "connected", "error", "unverified"}
    assert response.context["stats"] == {
        "total": 1,
        "active": 1,
        "connected": 1,
        "error": 0,
        "unverified": 0,
    }
    assert response.context["domain"] is None
    assert response.context["domain_choices"] == ProjectIntegrationConnector.DOMAIN_CHOICES
    assert response.context["provider_choices"] == ProjectIntegrationConnector.PROVIDER_CHOICES
    assert response.context["status_choices"] == ProjectIntegrationConnector.STATUS_CHOICES
    assert _integrationapihub_pks(response, "connectors") == [integrationapihub_connector_a.pk]
    assert integrationapihub_connector_b.pk not in _integrationapihub_pks(response, "connectors")
    project_ids = set(response.context["projects"].values_list("pk", flat=True))
    assert integrationapihub_project_a.pk in project_ids
    assert integrationapihub_project_b.pk not in project_ids
    assert "due_rotation" not in response.context
    assert integrationapihub_connector_a.number in _integrationapihub_body(response)
    assert integrationapihub_connector_a.name in _integrationapihub_body(response)
    assert integrationapihub_connector_b.name not in _integrationapihub_body(response)


@pytest.mark.parametrize(
    "route,domain,label,provider",
    [
        ("ixc_erp_list", "erp", "ERP & Finance", "sap"),
        ("ixc_crm_list", "crm", "CRM", "salesforce"),
        ("ixc_hris_list", "hris", "HR & Talent", "workday"),
        ("ixc_devops_list", "devops", "DevOps", "github"),
        ("ixc_storage_list", "storage", "File Storage", "sharepoint"),
    ],
)
def test_integrationapihub_connector_category_routes_scope_domain_and_content(
    client_a, tenant_a, integrationapihub_project_a, route, domain, label, provider,
):
    connector = _integrationapihub_connector(
        tenant_a,
        project=integrationapihub_project_a,
        name=f"Category {domain}",
        domain=domain,
        provider=provider,
        status="connected",
    )
    response = _integrationapihub_get(client_a, route, domain="custom")
    assert response.status_code == 200
    assert response.context["domain"] == domain
    assert _integrationapihub_pks(response, "connectors") == [connector.pk]
    assert all(row.domain == domain for row in response.context["connectors"])
    assert label in _integrationapihub_body(response)
    assert connector.number in _integrationapihub_body(response)


def test_integrationapihub_connector_list_applies_every_filter_and_combination(
    client_a, tenant_a, integrationapihub_project_a,
):
    match = _integrationapihub_connector(
        tenant_a,
        project=integrationapihub_project_a,
        name="Alpha filter connector",
        remote_scope_ref="SCOPE-ALPHA",
        status="connected",
        provider="sap",
        is_active=True,
    )
    other = _integrationapihub_connector(
        tenant_a,
        project=None,
        name="Beta filter connector",
        remote_scope_ref="SCOPE-BETA",
        status="error",
        provider="oracle",
        is_active=False,
    )
    cases = (
        ({"q": "  Alpha filter  "}, {match.pk}),
        ({"q": match.number}, {match.pk}),
        ({"q": "SCOPE-ALPHA"}, {match.pk}),
        ({"status": "connected"}, {match.pk}),
        ({"provider": "sap"}, {match.pk}),
        ({"project": str(integrationapihub_project_a.pk)}, {match.pk}),
        ({"is_active": "active"}, {match.pk}),
        ({"is_active": "true"}, {match.pk}),
        ({"is_active": "1"}, {match.pk}),
        ({"is_active": "inactive"}, {other.pk}),
        ({"is_active": "false"}, {other.pk}),
        ({"is_active": "0"}, {other.pk}),
        (
            {
                "q": "Alpha",
                "status": "connected",
                "provider": "sap",
                "project": str(integrationapihub_project_a.pk),
                "is_active": "active",
            },
            {match.pk},
        ),
    )
    for params, expected in cases:
        response = _integrationapihub_get(client_a, "ixc_list", **params)
        assert response.status_code == 200
        assert set(_integrationapihub_pks(response, "connectors")) == expected
        assert response.context["stats"]["total"] == 2
    response = _integrationapihub_get(
        client_a,
        "ixc_list",
        project="not-an-integer",
        is_active="unknown",
        page="999",
        junk="accepted",
    )
    assert response.status_code == 200
    assert set(_integrationapihub_pks(response, "connectors")) == {match.pk, other.pk}
    assert response.context["project_id"] == "not-an-integer"
    assert response.context["is_active"] == "unknown"
    unknown_status = _integrationapihub_get(client_a, "ixc_list", status="not-a-choice")
    assert unknown_status.status_code == 200
    assert _integrationapihub_pks(unknown_status, "connectors") == []
    assert unknown_status.context["status"] == "not-a-choice"


def test_integrationapihub_connector_pagination_is_25_and_preserves_active_filters(
    client_a, tenant_a,
):
    for index in range(1, 27):
        _integrationapihub_connector(
            tenant_a,
            project=None,
            name=f"Paged connector {index:02d}",
            status="connected",
            provider="sap",
            is_active=True,
        )
    page_one = _integrationapihub_get(client_a, "ixc_list", q="Paged connector", is_active="active")
    assert page_one.status_code == 200
    assert page_one.context["page_obj"].paginator.per_page == INTEGRATIONAPIHUB_PAGE_SIZE
    assert len(page_one.context["connectors"]) == INTEGRATIONAPIHUB_PAGE_SIZE
    assert "Paged connector 26" in _integrationapihub_body(page_one)
    assert _integrationapihub_page_query(page_one) == {
        "page": "2",
        "q": "Paged connector",
        "is_active": "active",
    }
    page_two = _integrationapihub_get(
        client_a, "ixc_list", page=2, q="Paged connector", is_active="active",
    )
    assert page_two.status_code == 200
    assert page_two.context["page_obj"].number == 2
    assert len(page_two.context["connectors"]) == 1
    assert "Paged connector 01" in _integrationapihub_body(page_two)
    large = _integrationapihub_get(
        client_a, "ixc_list", page=999, q="Paged connector", is_active="active",
    )
    assert large.status_code == 200
    assert large.context["page_obj"].number == 2
    assert len(large.context["connectors"]) == 1


def test_integrationapihub_connector_detail_keeps_full_mapping_total_with_capped_slice(
    client_a,
    integrationapihub_connector_a,
    integrationapihub_mapping_a,
    integrationapihub_job_a,
    integrationapihub_run_a,
):
    for _ in range(20):
        _integrationapihub_mapping(
            integrationapihub_connector_a.tenant,
            integrationapihub_connector_a,
        )
    response = _integrationapihub_get(client_a, "ixc_detail", integrationapihub_connector_a.pk)
    assert response.status_code == 200
    expected = {
        "connector", "mappings", "mappings_total", "jobs", "recent_runs", "test_form",
        "revealed_credential",
    }
    assert expected <= set(response.context.keys())
    assert response.context["connector"] == integrationapihub_connector_a
    assert len(response.context["mappings"]) == 20
    assert response.context["mappings_total"] == 21
    assert _integrationapihub_pks(response, "jobs") == [integrationapihub_job_a.pk]
    assert _integrationapihub_pks(response, "recent_runs") == [integrationapihub_run_a.pk]
    assert response.context["revealed_credential"] is None
    body = _integrationapihub_body(response)
    assert "Field Mappings (21)" in body
    assert integrationapihub_connector_a.number in body
    assert response.context["mappings"][0].local_field in body
    assert integrationapihub_job_a.number in body
    assert integrationapihub_run_a.number in body


def test_integrationapihub_connector_create_get_has_form_only_context(client_a, tenant_a):
    response = _integrationapihub_get(client_a, "ixc_create")
    assert response.status_code == 200
    assert set(response.context.keys()) & {"form", "is_edit", "connector"} == {"form"}
    assert response.context["form"].instance.tenant_id == tenant_a.pk
    assert "Create Connector" in _integrationapihub_body(response)


def test_integrationapihub_connector_create_valid_post_redirects_and_audits(
    client_a,
    tenant_a,
    admin_user,
    integrationapihub_project_a,
    workflowautomation_webhook_a,
):
    response = _integrationapihub_post(
        client_a,
        "ixc_create",
        data=_integrationapihub_connector_payload(
            project=integrationapihub_project_a,
            owner=admin_user,
            notify_webhook=str(workflowautomation_webhook_a.pk),
            name="Created through connector view",
            status="connected",
        ),
    )
    assert response.status_code == 302
    connector = ProjectIntegrationConnector.objects.get(
        tenant=tenant_a, name="Created through connector view",
    )
    assert response.url == _integrationapihub_url("ixc_detail", connector.pk)
    assert connector.project_id == integrationapihub_project_a.pk
    assert connector.owner_id == admin_user.pk
    assert connector.notify_webhook_id == workflowautomation_webhook_a.pk
    assert connector.status == "connected"
    assert _integrationapihub_audits(ProjectIntegrationConnector, connector.pk, "create")


def test_integrationapihub_connector_create_invalid_post_rerenders_with_errors(
    client_a, tenant_a,
):
    response = _integrationapihub_post(client_a, "ixc_create", data={"name": ""})
    assert response.status_code == 200
    assert response.context["form"].errors
    assert "is_edit" not in response.context
    assert "connector" not in response.context
    assert not ProjectIntegrationConnector.objects.filter(tenant=tenant_a).exists()


def test_integrationapihub_connector_edit_get_renders_object_context_and_content(
    client_a, admin_user, integrationapihub_connector_a,
):
    response = _integrationapihub_get(client_a, "ixc_edit", integrationapihub_connector_a.pk)
    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["connector"] == integrationapihub_connector_a
    assert response.context["form"].instance.pk == integrationapihub_connector_a.pk
    body = _integrationapihub_body(response)
    assert f"Edit Connector: {integrationapihub_connector_a.number}" in body
    assert integrationapihub_connector_a.name in body
    assert response.context["form"].fields["owner"].queryset.filter(pk=admin_user.pk).exists()


def test_integrationapihub_connector_edit_valid_post_preserves_blank_credential_and_audits(
    client_a,
    admin_user,
    integrationapihub_connector_credential_a,
):
    original_ciphertext = integrationapihub_connector_credential_a.credential
    response = _integrationapihub_post(
        client_a,
        "ixc_edit",
        integrationapihub_connector_credential_a.pk,
        data=_integrationapihub_connector_payload(
            project=integrationapihub_connector_credential_a.project,
            owner=admin_user,
            name="Edited credential connector",
            domain=integrationapihub_connector_credential_a.domain,
            provider=integrationapihub_connector_credential_a.provider,
            credential="",
            notes="Edited without replacing the stored credential.",
        ),
    )
    assert response.status_code == 302
    assert response.url == _integrationapihub_url(
        "ixc_detail", integrationapihub_connector_credential_a.pk,
    )
    integrationapihub_connector_credential_a.refresh_from_db()
    assert integrationapihub_connector_credential_a.name == "Edited credential connector"
    assert integrationapihub_connector_credential_a.credential == original_ciphertext
    assert integrationapihub_connector_credential_a.get_credential() == "provider-secret-1234"
    assert _integrationapihub_audits(
        ProjectIntegrationConnector, integrationapihub_connector_credential_a.pk, "update",
    )


def test_integrationapihub_connector_edit_invalid_post_preserves_row(
    client_a, admin_user, integrationapihub_connector_a,
):
    original_name = integrationapihub_connector_a.name
    response = _integrationapihub_post(
        client_a,
        "ixc_edit",
        integrationapihub_connector_a.pk,
        data=_integrationapihub_connector_payload(
            project=integrationapihub_connector_a.project,
            owner=admin_user,
            name="",
        ),
    )
    assert response.status_code == 200
    assert "name" in response.context["form"].errors
    assert response.context["is_edit"] is True
    integrationapihub_connector_a.refresh_from_db()
    assert integrationapihub_connector_a.name == original_name
    assert not _integrationapihub_audits(
        ProjectIntegrationConnector, integrationapihub_connector_a.pk, "update",
    )


def test_integrationapihub_connector_delete_cascades_mappings_jobs_and_runs(
    client_a,
    integrationapihub_connector_a,
    integrationapihub_mapping_a,
    integrationapihub_job_a,
    integrationapihub_run_a,
):
    connector_pk = integrationapihub_connector_a.pk
    mapping_pk = integrationapihub_mapping_a.pk
    job_pk = integrationapihub_job_a.pk
    run_pk = integrationapihub_run_a.pk
    response = _integrationapihub_post(client_a, "ixc_delete", connector_pk)
    assert response.status_code == 302
    assert response.url == _integrationapihub_url("ixc_list")
    assert not ProjectIntegrationConnector.objects.filter(pk=connector_pk).exists()
    assert not ConnectorFieldMapping.objects.filter(pk=mapping_pk).exists()
    assert not ProjectSyncJob.objects.filter(pk=job_pk).exists()
    assert not ProjectSyncRun.objects.filter(pk=run_pk).exists()
    audit = AuditLog.objects.filter(action="delete", changes__connector=integrationapihub_connector_a.number)
    assert audit.exists()


def test_integrationapihub_connector_test_records_truncated_note_without_transport(
    client_a,
    admin_user,
    integrationapihub_connector_a,
    integrationapihub_job_a,
):
    before_count = ProjectSyncRun.objects.filter(job=integrationapihub_job_a).count()
    note = f"  {'N' * 520}  "
    response = _integrationapihub_post(
        client_a,
        "ixc_test",
        integrationapihub_connector_a.pk,
        data={"note": note},
    )
    assert response.status_code == 302
    assert response.url == _integrationapihub_url("ixc_detail", integrationapihub_connector_a.pk)
    run = ProjectSyncRun.objects.filter(job=integrationapihub_job_a).order_by("-id").first()
    assert ProjectSyncRun.objects.filter(job=integrationapihub_job_a).count() == before_count + 1
    assert run.status == "simulated"
    assert run.trigger_source == "manual"
    assert run.triggered_by_id == admin_user.pk
    assert run.payload_excerpt == "N" * 500
    assert run.error_message == "Simulated connection test — no outbound request was made."
    integrationapihub_connector_a.refresh_from_db()
    integrationapihub_job_a.refresh_from_db()
    assert integrationapihub_connector_a.last_sync_at is not None
    assert integrationapihub_connector_a.last_success_at is None
    assert integrationapihub_connector_a.consecutive_failures == 0
    assert integrationapihub_connector_a.status == "connected"
    assert integrationapihub_job_a.run_count == 0
    assert integrationapihub_job_a.last_status == ""
    assert any("no request was sent" in message for message in _integrationapihub_messages(response))
    assert _integrationapihub_audits(
        ProjectIntegrationConnector, integrationapihub_connector_a.pk, "test",
    )


def test_integrationapihub_connector_test_without_job_warns_and_creates_nothing(
    client_a,
    integrationapihub_connector_workspace_a,
):
    response = _integrationapihub_post(
        client_a,
        "ixc_test",
        integrationapihub_connector_workspace_a.pk,
        data={"note": "This must not create a run."},
    )
    assert response.status_code == 302
    assert response.url == _integrationapihub_url(
        "ixc_detail", integrationapihub_connector_workspace_a.pk,
    )
    assert _integrationapihub_messages(response) == [
        "Create a sync job for this connector before running a test."
    ]
    assert not ProjectSyncJob.objects.filter(connector=integrationapihub_connector_workspace_a).exists()
    assert not ProjectSyncRun.objects.filter(
        job__connector=integrationapihub_connector_workspace_a,
    ).exists()
    integrationapihub_connector_workspace_a.refresh_from_db()
    assert integrationapihub_connector_workspace_a.last_sync_at is None
    assert not _integrationapihub_audits(
        ProjectIntegrationConnector,
        integrationapihub_connector_workspace_a.pk,
        "test",
    )


def test_integrationapihub_connector_toggle_flips_only_active_state_and_audits(
    client_a, integrationapihub_connector_a,
):
    original_status = integrationapihub_connector_a.status
    for expected in (False, True):
        response = _integrationapihub_post(
            client_a, "ixc_toggle_active", integrationapihub_connector_a.pk,
        )
        assert response.status_code == 302
        integrationapihub_connector_a.refresh_from_db()
        assert integrationapihub_connector_a.is_active is expected
        assert integrationapihub_connector_a.status == original_status
    audits = _integrationapihub_audits(
        ProjectIntegrationConnector, integrationapihub_connector_a.pk, "toggle",
    )
    assert [row.changes["is_active"] for row in audits] == [False, True]


def test_integrationapihub_connector_rotate_replaces_cipher_and_reveals_once(
    client_a, integrationapihub_connector_credential_a,
):
    old_ciphertext = integrationapihub_connector_credential_a.credential
    response = _integrationapihub_post(
        client_a, "ixc_rotate_credential", integrationapihub_connector_credential_a.pk,
    )
    assert response.status_code == 302
    integrationapihub_connector_credential_a.refresh_from_db()
    new_secret = integrationapihub_connector_credential_a.get_credential()
    assert integrationapihub_connector_credential_a.credential != old_ciphertext
    assert re.fullmatch(r"[0-9a-f]{64}", new_secret)
    assert new_secret != "provider-secret-1234"
    first = _integrationapihub_get(
        client_a, "ixc_detail", integrationapihub_connector_credential_a.pk,
    )
    assert first.status_code == 200
    assert first.context["revealed_credential"] == new_secret
    assert new_secret in _integrationapihub_body(first)
    second = _integrationapihub_get(
        client_a, "ixc_detail", integrationapihub_connector_credential_a.pk,
    )
    assert second.status_code == 200
    assert second.context["revealed_credential"] is None
    assert new_secret not in _integrationapihub_body(second)
    messages = _integrationapihub_messages(response)
    audits = _integrationapihub_audits(
        ProjectIntegrationConnector, integrationapihub_connector_credential_a.pk, "rotate",
    )
    assert messages
    assert new_secret not in " ".join(messages)
    assert new_secret not in json.dumps([row.changes for row in audits])


def test_integrationapihub_connector_detail_query_cost_is_flat_in_recent_runs(
    client_a,
    tenant_a,
    integrationapihub_connector_a,
    django_assert_max_num_queries,
):
    job = _integrationapihub_job(
        tenant_a, integrationapihub_connector_a, name="Query budget job",
    )
    _integrationapihub_run(tenant_a, job)
    _integrationapihub_run(tenant_a, job)
    _integrationapihub_get(client_a, "ixc_detail", integrationapihub_connector_a.pk)
    baseline, _ = _integrationapihub_measure(
        client_a, "ixc_detail", integrationapihub_connector_a.pk,
    )
    for _ in range(13):
        _integrationapihub_run(tenant_a, job)
    with django_assert_max_num_queries(baseline):
        response = _integrationapihub_get(
            client_a, "ixc_detail", integrationapihub_connector_a.pk,
        )
    assert response.status_code == 200
    assert len(response.context["recent_runs"]) == 15


def test_integrationapihub_connector_health_renders_aggregate_counts_and_content(
    client_a,
    integrationapihub_connector_a,
    integrationapihub_mapping_a,
    integrationapihub_job_a,
    integrationapihub_run_a,
    integrationapihub_run_failed_a,
):
    success_run = _integrationapihub_run(
        integrationapihub_connector_a.tenant,
        integrationapihub_job_a,
        status="success",
    )
    last_success = timezone.now() - timedelta(hours=2)
    integrationapihub_connector_a.last_success_at = last_success
    integrationapihub_connector_a.save(update_fields=["last_success_at", "updated_at"])
    response = _integrationapihub_get(
        client_a, "connector_health", integrationapihub_connector_a.pk,
    )
    assert response.status_code == 200
    expected = {"connector", "recent_runs", "jobs_count", "mappings_count", "stats"}
    assert expected <= set(response.context.keys())
    assert set(response.context["stats"]) == {
        "total_runs", "failed_runs", "success_rate", "last_success_at",
    }
    assert response.context["stats"] == {
        "total_runs": 3,
        "failed_runs": 1,
        "success_rate": 33,
        "last_success_at": last_success,
    }
    assert response.context["jobs_count"] == 1
    assert response.context["mappings_count"] == 1
    assert {run.pk for run in response.context["recent_runs"]} == {
        success_run.pk,
        integrationapihub_run_a.pk,
        integrationapihub_run_failed_a.pk,
    }
    body = _integrationapihub_body(response)
    assert integrationapihub_connector_a.number in body
    assert "33%" in body
    assert integrationapihub_run_failed_a.number in body


def test_integrationapihub_connector_health_query_cost_is_flat_in_run_count(
    client_a,
    tenant_a,
    integrationapihub_connector_a,
    django_assert_max_num_queries,
):
    job = _integrationapihub_job(
        tenant_a, integrationapihub_connector_a, name="Health query job",
    )
    _integrationapihub_run(tenant_a, job)
    _integrationapihub_run(tenant_a, job)
    _integrationapihub_get(client_a, "connector_health", integrationapihub_connector_a.pk)
    baseline, _ = _integrationapihub_measure(
        client_a, "connector_health", integrationapihub_connector_a.pk,
    )
    for _ in range(18):
        _integrationapihub_run(tenant_a, job)
    with django_assert_max_num_queries(baseline):
        response = _integrationapihub_get(
            client_a, "connector_health", integrationapihub_connector_a.pk,
        )
    assert response.status_code == 200
    assert len(response.context["recent_runs"]) == 15


def test_integrationapihub_mapping_list_renders_context_content_and_tenant_scope(
    client_a,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
    integrationapihub_mapping_a,
    integrationapihub_mapping_b,
):
    response = _integrationapihub_get(client_a, "ixm_list")
    assert response.status_code == 200
    expected = {
        "mappings", "page_obj", "connectors", "connector_id", "direction", "transform",
        "direction_choices", "transform_choices", "q",
    }
    assert expected <= set(response.context.keys())
    assert _integrationapihub_pks(response, "mappings") == [integrationapihub_mapping_a.pk]
    assert integrationapihub_mapping_b.pk not in _integrationapihub_pks(response, "mappings")
    assert integrationapihub_connector_b.pk not in set(
        response.context["connectors"].values_list("pk", flat=True),
    )
    assert response.context["direction_choices"] == ConnectorFieldMapping.DIRECTION_CHOICES
    assert response.context["transform_choices"] == ConnectorFieldMapping.TRANSFORM_CHOICES
    body = _integrationapihub_body(response)
    assert integrationapihub_mapping_a.local_field in body
    assert integrationapihub_mapping_a.remote_field in body
    assert integrationapihub_mapping_b.local_field not in body


def test_integrationapihub_mapping_list_applies_every_filter_and_combination(
    client_a, tenant_a, integrationapihub_connector_a,
):
    other_connector = _integrationapihub_connector(
        tenant_a, project=None, name="Mapping filter second connector",
    )
    match = _integrationapihub_mapping(
        tenant_a,
        integrationapihub_connector_a,
        local_field="task.filter_key",
        remote_field="fields.FilterKey",
        direction="to_remote",
        transform="upper",
    )
    other = _integrationapihub_mapping(
        tenant_a,
        other_connector,
        local_field="client.filter_name",
        remote_field="Account.FilterName",
        direction="from_remote",
        transform="trim",
    )
    cases = (
        ({"q": "filter_key"}, {match.pk}),
        ({"q": "Account.FilterName"}, {other.pk}),
        ({"connector": str(integrationapihub_connector_a.pk)}, {match.pk}),
        ({"direction": "to_remote"}, {match.pk}),
        ({"transform": "upper"}, {match.pk}),
        (
            {
                "q": "filter_key",
                "connector": str(integrationapihub_connector_a.pk),
                "direction": "to_remote",
                "transform": "upper",
            },
            {match.pk},
        ),
    )
    for params, expected in cases:
        response = _integrationapihub_get(client_a, "ixm_list", **params)
        assert response.status_code == 200
        assert set(_integrationapihub_pks(response, "mappings")) == expected
    response = _integrationapihub_get(
        client_a,
        "ixm_list",
        connector="junk",
        direction="sideways",
        transform="not-a-transform",
        page="999",
    )
    assert response.status_code == 200
    assert _integrationapihub_pks(response, "mappings") == []
    assert response.context["connector_id"] == "junk"
    assert response.context["direction"] == "sideways"
    assert response.context["transform"] == "not-a-transform"
    ignored = _integrationapihub_get(client_a, "ixm_list", connector="junk")
    assert set(_integrationapihub_pks(ignored, "mappings")) == {match.pk, other.pk}


def test_integrationapihub_mapping_pagination_is_25_and_preserves_active_filters(
    client_a, integrationapihub_connector_a,
):
    for _ in range(26):
        _integrationapihub_mapping(
            integrationapihub_connector_a.tenant,
            integrationapihub_connector_a,
            direction="both",
            transform="none",
        )
    params = {
        "q": "task.field",
        "connector": str(integrationapihub_connector_a.pk),
        "direction": "both",
        "transform": "none",
    }
    page_one = _integrationapihub_get(client_a, "ixm_list", **params)
    assert page_one.status_code == 200
    assert page_one.context["page_obj"].paginator.per_page == INTEGRATIONAPIHUB_PAGE_SIZE
    assert len(page_one.context["mappings"]) == INTEGRATIONAPIHUB_PAGE_SIZE
    assert _integrationapihub_page_query(page_one) == {"page": "2", **params}
    page_two = _integrationapihub_get(client_a, "ixm_list", page=2, **params)
    assert page_two.status_code == 200
    assert page_two.context["page_obj"].number == 2
    assert len(page_two.context["mappings"]) == 1
    large = _integrationapihub_get(client_a, "ixm_list", page=999, **params)
    assert large.status_code == 200
    assert large.context["page_obj"].number == 2
    assert len(large.context["mappings"]) == 1


def test_integrationapihub_mapping_detail_renders_object_context_and_content(
    client_a, integrationapihub_mapping_a,
):
    response = _integrationapihub_get(client_a, "ixm_detail", integrationapihub_mapping_a.pk)
    assert response.status_code == 200
    assert response.context["mapping"] == integrationapihub_mapping_a
    body = _integrationapihub_body(response)
    assert integrationapihub_mapping_a.local_field in body
    assert integrationapihub_mapping_a.remote_field in body
    assert integrationapihub_mapping_a.connector.number in body
    assert "To Do" in body


def test_integrationapihub_mapping_create_get_has_form_only_context(client_a, tenant_a):
    response = _integrationapihub_get(client_a, "ixm_create")
    assert response.status_code == 200
    assert set(response.context.keys()) & {"form", "is_edit", "mapping"} == {"form"}
    assert response.context["form"].instance.tenant_id == tenant_a.pk
    assert "Create Field Mapping" in _integrationapihub_body(response)


def test_integrationapihub_mapping_create_valid_post_redirects_and_audits(
    client_a, tenant_a, integrationapihub_connector_a,
):
    response = _integrationapihub_post(
        client_a,
        "ixm_create",
        data=_integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="task.view_created",
            remote_field="fields.ViewCreated",
            value_map='{"todo": "To Do"}',
            is_key="on",
            is_required="on",
        ),
    )
    assert response.status_code == 302
    mapping = ConnectorFieldMapping.objects.get(
        tenant=tenant_a, local_field="task.view_created",
    )
    assert response.url == _integrationapihub_url("ixm_detail", mapping.pk)
    assert mapping.value_map == {"todo": "To Do"}
    assert mapping.is_key is True
    assert mapping.is_required is True
    assert _integrationapihub_audits(ConnectorFieldMapping, mapping.pk, "create")


def test_integrationapihub_mapping_create_invalid_post_rerenders_with_errors(
    client_a, tenant_a, integrationapihub_connector_a,
):
    response = _integrationapihub_post(
        client_a,
        "ixm_create",
        data=_integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="",
            remote_field="",
            value_map="{not-json",
        ),
    )
    assert response.status_code == 200
    assert "local_field" in response.context["form"].errors
    assert "remote_field" in response.context["form"].errors
    assert "value_map" in response.context["form"].errors
    assert not ConnectorFieldMapping.objects.filter(tenant=tenant_a).exists()


def test_integrationapihub_mapping_edit_get_renders_object_context_and_content(
    client_a, integrationapihub_mapping_a,
):
    response = _integrationapihub_get(client_a, "ixm_edit", integrationapihub_mapping_a.pk)
    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["mapping"] == integrationapihub_mapping_a
    assert response.context["form"].instance.pk == integrationapihub_mapping_a.pk
    body = _integrationapihub_body(response)
    assert "Edit Field Mapping" in body
    assert integrationapihub_mapping_a.local_field in body


def test_integrationapihub_mapping_edit_valid_post_redirects_and_audits(
    client_a, integrationapihub_connector_a, integrationapihub_mapping_a,
):
    response = _integrationapihub_post(
        client_a,
        "ixm_edit",
        integrationapihub_mapping_a.pk,
        data=_integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="task.status_edited",
            remote_field="fields.status.edited",
            direction="both",
            transform="lower",
            value_map='{"done": "complete"}',
            is_required="on",
        ),
    )
    assert response.status_code == 302
    assert response.url == _integrationapihub_url("ixm_detail", integrationapihub_mapping_a.pk)
    integrationapihub_mapping_a.refresh_from_db()
    assert integrationapihub_mapping_a.local_field == "task.status_edited"
    assert integrationapihub_mapping_a.remote_field == "fields.status.edited"
    assert integrationapihub_mapping_a.transform == "lower"
    assert integrationapihub_mapping_a.value_map == {"done": "complete"}
    assert _integrationapihub_audits(
        ConnectorFieldMapping, integrationapihub_mapping_a.pk, "update",
    )


def test_integrationapihub_mapping_edit_invalid_post_preserves_row(
    client_a, integrationapihub_connector_a, integrationapihub_mapping_a,
):
    original_remote = integrationapihub_mapping_a.remote_field
    response = _integrationapihub_post(
        client_a,
        "ixm_edit",
        integrationapihub_mapping_a.pk,
        data=_integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field=integrationapihub_mapping_a.local_field,
            remote_field="",
            direction=integrationapihub_mapping_a.direction,
            transform=integrationapihub_mapping_a.transform,
        ),
    )
    assert response.status_code == 200
    assert "remote_field" in response.context["form"].errors
    integrationapihub_mapping_a.refresh_from_db()
    assert integrationapihub_mapping_a.remote_field == original_remote
    assert not _integrationapihub_audits(
        ConnectorFieldMapping, integrationapihub_mapping_a.pk, "update",
    )


def test_integrationapihub_mapping_delete_redirects_removes_and_audits(
    client_a, integrationapihub_mapping_a,
):
    label = (
        f"{integrationapihub_mapping_a.local_field} → "
        f"{integrationapihub_mapping_a.remote_field}"
    )
    response = _integrationapihub_post(client_a, "ixm_delete", integrationapihub_mapping_a.pk)
    assert response.status_code == 302
    assert response.url == _integrationapihub_url("ixm_list")
    assert not ConnectorFieldMapping.objects.filter(pk=integrationapihub_mapping_a.pk).exists()
    assert AuditLog.objects.filter(action="delete", changes__mapping=label).exists()


def test_integrationapihub_job_list_renders_context_content_and_tenant_scope(
    client_a,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
    integrationapihub_job_a,
    integrationapihub_job_b,
    integrationapihub_run_a,
):
    response = _integrationapihub_get(client_a, "syj_list")
    assert response.status_code == 200
    expected = {
        "jobs", "page_obj", "connectors", "entity_choices", "trigger_choices",
        "conflict_choices", "status_choices", "q", "connector_id", "entity_scope",
        "trigger_mode", "is_active", "stats",
    }
    assert expected <= set(response.context.keys())
    assert set(response.context["stats"]) == {"total", "active", "inactive", "runs_total"}
    assert response.context["stats"] == {
        "total": 1,
        "active": 1,
        "inactive": 0,
        "runs_total": 1,
    }
    assert response.context["entity_choices"] == ProjectSyncJob.SYNC_ENTITY_CHOICES
    assert response.context["trigger_choices"] == ProjectSyncJob.TRIGGER_MODE_CHOICES
    assert response.context["conflict_choices"] == ProjectSyncJob.CONFLICT_POLICY_CHOICES
    assert response.context["status_choices"] == ProjectSyncRun.RUN_STATUS_CHOICES
    assert _integrationapihub_pks(response, "jobs") == [integrationapihub_job_a.pk]
    assert integrationapihub_job_b.pk not in _integrationapihub_pks(response, "jobs")
    assert integrationapihub_connector_b.pk not in set(
        response.context["connectors"].values_list("pk", flat=True),
    )
    body = _integrationapihub_body(response)
    assert integrationapihub_job_a.number in body
    assert integrationapihub_job_a.name in body
    assert integrationapihub_job_b.name not in body


def test_integrationapihub_job_list_applies_every_filter_and_combination(
    client_a, tenant_a, integrationapihub_connector_a,
):
    other_connector = _integrationapihub_connector(
        tenant_a, project=None, name="Job filter second connector",
    )
    match = _integrationapihub_job(
        tenant_a,
        integrationapihub_connector_a,
        name="Alpha scheduled job",
        entity_scope="issues",
        trigger_mode="scheduled",
        is_active=True,
    )
    other = _integrationapihub_job(
        tenant_a,
        other_connector,
        name="Beta event job",
        entity_scope="documents",
        trigger_mode="event",
        is_active=False,
    )
    cases = (
        ({"q": "Alpha scheduled"}, {match.pk}),
        ({"q": match.number}, {match.pk}),
        ({"connector": str(integrationapihub_connector_a.pk)}, {match.pk}),
        ({"entity_scope": "issues"}, {match.pk}),
        ({"trigger_mode": "scheduled"}, {match.pk}),
        ({"is_active": "active"}, {match.pk}),
        ({"is_active": "true"}, {match.pk}),
        ({"is_active": "1"}, {match.pk}),
        ({"is_active": "inactive"}, {other.pk}),
        ({"is_active": "false"}, {other.pk}),
        ({"is_active": "0"}, {other.pk}),
        (
            {
                "q": "Alpha",
                "connector": str(integrationapihub_connector_a.pk),
                "entity_scope": "issues",
                "trigger_mode": "scheduled",
                "is_active": "active",
            },
            {match.pk},
        ),
    )
    for params, expected in cases:
        response = _integrationapihub_get(client_a, "syj_list", **params)
        assert response.status_code == 200
        assert set(_integrationapihub_pks(response, "jobs")) == expected
        assert response.context["stats"]["total"] == 2
    response = _integrationapihub_get(
        client_a,
        "syj_list",
        connector="not-a-pk",
        entity_scope="unknown",
        trigger_mode="never",
        is_active="maybe",
        page="999",
    )
    assert response.status_code == 200
    assert _integrationapihub_pks(response, "jobs") == []
    assert response.context["connector_id"] == "not-a-pk"
    assert response.context["entity_scope"] == "unknown"
    assert response.context["trigger_mode"] == "never"
    assert response.context["is_active"] == "maybe"
    ignored = _integrationapihub_get(client_a, "syj_list", connector="not-a-pk")
    assert set(_integrationapihub_pks(ignored, "jobs")) == {match.pk, other.pk}


def test_integrationapihub_job_pagination_is_25_and_preserves_active_filters(
    client_a, tenant_a, integrationapihub_connector_a,
):
    for _ in range(26):
        _integrationapihub_job(
            tenant_a,
            integrationapihub_connector_a,
            entity_scope="tasks",
            trigger_mode="manual",
            is_active=True,
        )
    params = {
        "q": "SYJ-",
        "connector": str(integrationapihub_connector_a.pk),
        "entity_scope": "tasks",
        "trigger_mode": "manual",
        "is_active": "active",
    }
    page_one = _integrationapihub_get(client_a, "syj_list", **params)
    assert page_one.status_code == 200
    assert page_one.context["page_obj"].paginator.per_page == INTEGRATIONAPIHUB_PAGE_SIZE
    assert len(page_one.context["jobs"]) == INTEGRATIONAPIHUB_PAGE_SIZE
    assert _integrationapihub_page_query(page_one) == {"page": "2", **params}
    page_two = _integrationapihub_get(client_a, "syj_list", page=2, **params)
    assert page_two.status_code == 200
    assert page_two.context["page_obj"].number == 2
    assert len(page_two.context["jobs"]) == 1
    large = _integrationapihub_get(client_a, "syj_list", page=999, **params)
    assert large.status_code == 200
    assert large.context["page_obj"].number == 2
    assert len(large.context["jobs"]) == 1


def test_integrationapihub_job_detail_renders_object_context_and_content(
    client_a, integrationapihub_job_a, integrationapihub_connector_a, integrationapihub_run_a,
):
    response = _integrationapihub_get(client_a, "syj_detail", integrationapihub_job_a.pk)
    assert response.status_code == 200
    assert response.context["job"] == integrationapihub_job_a
    assert response.context["connector"] == integrationapihub_connector_a
    assert _integrationapihub_pks(response, "runs") == [integrationapihub_run_a.pk]
    body = _integrationapihub_body(response)
    assert integrationapihub_job_a.number in body
    assert integrationapihub_job_a.name in body
    assert integrationapihub_connector_a.number in body
    assert integrationapihub_run_a.number in body


def test_integrationapihub_job_create_get_has_form_only_context(client_a, tenant_a):
    response = _integrationapihub_get(client_a, "syj_create")
    assert response.status_code == 200
    assert set(response.context.keys()) & {"form", "is_edit", "job"} == {"form"}
    assert response.context["form"].instance.tenant_id == tenant_a.pk
    assert "Create Sync Job" in _integrationapihub_body(response)


def test_integrationapihub_job_create_valid_post_redirects_and_audits(
    client_a, tenant_a, integrationapihub_connector_a,
):
    response = _integrationapihub_post(
        client_a,
        "syj_create",
        data=_integrationapihub_job_payload(
            integrationapihub_connector_a,
            name="Created through job view",
            entity_scope="risks",
            interval_minutes="30",
            filter_expression="status == open",
            batch_size="25",
        ),
    )
    assert response.status_code == 302
    job = ProjectSyncJob.objects.get(tenant=tenant_a, name="Created through job view")
    assert response.url == _integrationapihub_url("syj_detail", job.pk)
    assert job.entity_scope == "risks"
    assert job.interval_minutes == 30
    assert job.filter_expression == "status == open"
    assert job.batch_size == 25
    assert _integrationapihub_audits(ProjectSyncJob, job.pk, "create")


def test_integrationapihub_job_create_invalid_post_rerenders_with_errors(
    client_a, tenant_a, integrationapihub_connector_a,
):
    response = _integrationapihub_post(
        client_a,
        "syj_create",
        data=_integrationapihub_job_payload(
            integrationapihub_connector_a,
            name="",
            entity_scope="unknown",
            batch_size="0.5",
        ),
    )
    assert response.status_code == 200
    assert "name" in response.context["form"].errors
    assert "entity_scope" in response.context["form"].errors
    assert "batch_size" in response.context["form"].errors
    assert not ProjectSyncJob.objects.filter(tenant=tenant_a).exists()


def test_integrationapihub_job_edit_get_renders_object_context_and_content(
    client_a, integrationapihub_job_a,
):
    response = _integrationapihub_get(client_a, "syj_edit", integrationapihub_job_a.pk)
    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["job"] == integrationapihub_job_a
    assert response.context["form"].instance.pk == integrationapihub_job_a.pk
    body = _integrationapihub_body(response)
    assert f"Edit Sync Job: {integrationapihub_job_a.number}" in body
    assert integrationapihub_job_a.name in body


def test_integrationapihub_job_edit_valid_post_redirects_and_audits(
    client_a, integrationapihub_job_a,
):
    response = _integrationapihub_post(
        client_a,
        "syj_edit",
        integrationapihub_job_a.pk,
        data=_integrationapihub_job_payload(
            integrationapihub_job_a.connector,
            name="Edited through job view",
            entity_scope="milestones",
            direction="inbound",
            trigger_mode="event",
            conflict_policy="remote_wins",
            batch_size="75",
        ),
    )
    assert response.status_code == 302
    assert response.url == _integrationapihub_url("syj_detail", integrationapihub_job_a.pk)
    integrationapihub_job_a.refresh_from_db()
    assert integrationapihub_job_a.name == "Edited through job view"
    assert integrationapihub_job_a.entity_scope == "milestones"
    assert integrationapihub_job_a.direction == "inbound"
    assert integrationapihub_job_a.trigger_mode == "event"
    assert integrationapihub_job_a.conflict_policy == "remote_wins"
    assert integrationapihub_job_a.batch_size == 75
    assert _integrationapihub_audits(ProjectSyncJob, integrationapihub_job_a.pk, "update")


def test_integrationapihub_job_edit_invalid_post_preserves_system_fields(
    client_a, integrationapihub_job_a,
):
    original_name = integrationapihub_job_a.name
    original_count = integrationapihub_job_a.run_count
    response = _integrationapihub_post(
        client_a,
        "syj_edit",
        integrationapihub_job_a.pk,
        data=_integrationapihub_job_payload(
            integrationapihub_job_a.connector,
            name="",
            run_count="999",
            last_status="success",
        ),
    )
    assert response.status_code == 200
    assert "name" in response.context["form"].errors
    integrationapihub_job_a.refresh_from_db()
    assert integrationapihub_job_a.name == original_name
    assert integrationapihub_job_a.run_count == original_count
    assert integrationapihub_job_a.last_status == ""
    assert not _integrationapihub_audits(ProjectSyncJob, integrationapihub_job_a.pk, "update")


def test_integrationapihub_job_delete_cascades_runs_and_audits(
    client_a, integrationapihub_job_a, integrationapihub_run_a,
):
    job_pk = integrationapihub_job_a.pk
    run_pk = integrationapihub_run_a.pk
    response = _integrationapihub_post(client_a, "syj_delete", job_pk)
    assert response.status_code == 302
    assert response.url == _integrationapihub_url("syj_list")
    assert not ProjectSyncJob.objects.filter(pk=job_pk).exists()
    assert not ProjectSyncRun.objects.filter(pk=run_pk).exists()
    assert AuditLog.objects.filter(
        action="delete", changes__sync_job=integrationapihub_job_a.number,
    ).exists()


def test_integrationapihub_job_toggle_flips_only_active_state_and_audits(
    client_a, integrationapihub_job_a,
):
    original_status = integrationapihub_job_a.last_status
    for expected in (False, True):
        response = _integrationapihub_post(
            client_a, "syj_toggle_active", integrationapihub_job_a.pk,
        )
        assert response.status_code == 302
        integrationapihub_job_a.refresh_from_db()
        assert integrationapihub_job_a.is_active is expected
        assert integrationapihub_job_a.last_status == original_status
    audits = _integrationapihub_audits(ProjectSyncJob, integrationapihub_job_a.pk, "toggle")
    assert [row.changes["is_active"] for row in audits] == [False, True]


def test_integrationapihub_job_run_records_simulated_run_and_updates_system_fields(
    client_a,
    admin_user,
    integrationapihub_connector_a,
    integrationapihub_job_a,
):
    before_count = ProjectSyncRun.objects.filter(job=integrationapihub_job_a).count()
    response = _integrationapihub_post(client_a, "syj_run", integrationapihub_job_a.pk)
    assert response.status_code == 302
    assert response.url == _integrationapihub_url("syj_detail", integrationapihub_job_a.pk)
    run = ProjectSyncRun.objects.filter(job=integrationapihub_job_a).order_by("-id").first()
    assert ProjectSyncRun.objects.filter(job=integrationapihub_job_a).count() == before_count + 1
    assert run.status == "simulated"
    assert run.trigger_source == "manual"
    assert run.triggered_by_id == admin_user.pk
    assert run.started_at == run.finished_at
    assert run.error_message == "Simulated run — no outbound request was made."
    integrationapihub_job_a.refresh_from_db()
    integrationapihub_connector_a.refresh_from_db()
    assert integrationapihub_job_a.run_count == 1
    assert integrationapihub_job_a.last_run_at == run.started_at
    assert integrationapihub_job_a.last_status == "simulated"
    assert integrationapihub_connector_a.last_sync_at is None
    assert integrationapihub_connector_a.last_success_at is None
    assert any("no request was sent" in message for message in _integrationapihub_messages(response))
    assert _integrationapihub_audits(ProjectSyncJob, integrationapihub_job_a.pk, "run")


def test_integrationapihub_run_list_renders_context_content_and_tenant_scope(
    client_a,
    integrationapihub_job_a,
    integrationapihub_job_b,
    integrationapihub_run_a,
    integrationapihub_run_failed_a,
    integrationapihub_run_b,
):
    response = _integrationapihub_get(client_a, "syr_list")
    assert response.status_code == 200
    expected = {
        "runs", "page_obj", "jobs", "connectors", "status_choices", "trigger_choices", "stats",
        "q", "job_id", "connector_id", "status", "trigger_source", "date_from", "date_to",
    }
    assert expected <= set(response.context.keys())
    assert set(response.context["stats"]) == {
        "pending", "running", "failed", "partial", "simulated", "failed_today",
    }
    assert response.context["stats"] == {
        "pending": 0,
        "running": 0,
        "failed": 1,
        "partial": 0,
        "simulated": 1,
        "failed_today": 1,
    }
    assert response.context["status_choices"] == ProjectSyncRun.RUN_STATUS_CHOICES
    assert response.context["trigger_choices"] == ProjectSyncRun.TRIGGER_SOURCE_CHOICES
    run_ids = set(_integrationapihub_pks(response, "runs"))
    assert {integrationapihub_run_a.pk, integrationapihub_run_failed_a.pk} <= run_ids
    assert integrationapihub_run_b.pk not in run_ids
    assert integrationapihub_job_b.pk not in set(response.context["jobs"].values_list("pk", flat=True))
    body = _integrationapihub_body(response)
    assert integrationapihub_run_a.number in body
    assert integrationapihub_run_failed_a.number in body
    assert integrationapihub_job_b.name not in body


@pytest.mark.parametrize("route", ["syr_list", "sync_monitor"])
def test_integrationapihub_run_registers_apply_every_shared_filter(
    client_a,
    tenant_a,
    integrationapihub_connector_a,
    integrationapihub_job_a,
    integrationapihub_run_a,
    integrationapihub_run_failed_a,
    route,
):
    success_run = _integrationapihub_run(
        tenant_a,
        integrationapihub_job_a,
        status="success",
        trigger_source="schedule",
        error_message="Success filter needle",
    )
    today = timezone.localdate().isoformat()
    cases = (
        ({"q": integrationapihub_run_a.number}, {integrationapihub_run_a.pk}),
        ({"q": "partner timed out"}, {integrationapihub_run_failed_a.pk}),
        ({"job": str(integrationapihub_job_a.pk)}, {
            integrationapihub_run_a.pk,
            integrationapihub_run_failed_a.pk,
            success_run.pk,
        }),
        ({"connector": str(integrationapihub_connector_a.pk)}, {
            integrationapihub_run_a.pk,
            integrationapihub_run_failed_a.pk,
            success_run.pk,
        }),
        ({"status": "failed"}, {integrationapihub_run_failed_a.pk}),
        ({"trigger_source": "event"}, {integrationapihub_run_failed_a.pk}),
        ({"date_from": today}, {
            integrationapihub_run_a.pk,
            integrationapihub_run_failed_a.pk,
            success_run.pk,
        }),
        ({"date_to": today}, {
            integrationapihub_run_a.pk,
            integrationapihub_run_failed_a.pk,
            success_run.pk,
        }),
        (
            {
                "q": success_run.number,
                "job": str(integrationapihub_job_a.pk),
                "connector": str(integrationapihub_connector_a.pk),
                "status": "success",
                "trigger_source": "schedule",
                "date_from": today,
                "date_to": today,
            },
            {success_run.pk},
        ),
    )
    for params, expected in cases:
        response = _integrationapihub_get(client_a, route, **params)
        assert response.status_code == 200
        assert set(_integrationapihub_pks(response, "runs")) == expected
    empty = _integrationapihub_get(
        client_a,
        route,
        status="not-a-status",
        trigger_source="not-a-trigger",
        date_from="not-a-date",
        date_to="2026-13-40",
        job="not-a-pk",
        page="999",
    )
    assert empty.status_code == 200
    assert _integrationapihub_pks(empty, "runs") == []
    assert empty.context["status"] == "not-a-status"
    assert empty.context["trigger_source"] == "not-a-trigger"
    assert empty.context["date_from"] == "not-a-date"
    assert empty.context["date_to"] == "2026-13-40"
    assert empty.context["job_id"] == "not-a-pk"
    ignored = _integrationapihub_get(client_a, route, job="not-a-pk")
    assert set(_integrationapihub_pks(ignored, "runs")) == {
        integrationapihub_run_a.pk,
        integrationapihub_run_failed_a.pk,
        success_run.pk,
    }


@pytest.mark.parametrize("route", ["syr_list", "sync_monitor"])
def test_integrationapihub_run_register_pagination_is_25_and_preserves_every_filter(
    client_a,
    tenant_a,
    integrationapihub_connector_a,
    route,
):
    job = _integrationapihub_job(tenant_a, integrationapihub_connector_a, name="Paged run job")
    today = timezone.localtime()
    for index in range(1, 27):
        _integrationapihub_run(
            tenant_a,
            job,
            status="simulated",
            trigger_source="manual",
            error_message="Paged run marker",
            started_at=today - timedelta(minutes=index),
        )
    params = {
        "q": "Paged run marker",
        "status": "simulated",
        "job": str(job.pk),
        "connector": str(integrationapihub_connector_a.pk),
        "trigger_source": "manual",
        "date_from": timezone.localdate().isoformat(),
        "date_to": timezone.localdate().isoformat(),
    }
    page_one = _integrationapihub_get(client_a, route, **params)
    assert page_one.status_code == 200
    assert page_one.context["page_obj"].paginator.per_page == INTEGRATIONAPIHUB_PAGE_SIZE
    assert len(page_one.context["runs"]) == INTEGRATIONAPIHUB_PAGE_SIZE
    assert _integrationapihub_page_query(page_one) == {"page": "2", **params}
    page_two = _integrationapihub_get(client_a, route, page=2, **params)
    assert page_two.status_code == 200
    assert page_two.context["page_obj"].number == 2
    assert len(page_two.context["runs"]) == 1
    large = _integrationapihub_get(client_a, route, page=999, **params)
    assert large.status_code == 200
    assert large.context["page_obj"].number == 2
    assert len(large.context["runs"]) == 1


def test_integrationapihub_run_detail_renders_object_context_and_content(
    client_a, integrationapihub_run_failed_a,
):
    response = _integrationapihub_get(client_a, "syr_detail", integrationapihub_run_failed_a.pk)
    assert response.status_code == 200
    assert response.context["run"] == integrationapihub_run_failed_a
    body = _integrationapihub_body(response)
    assert integrationapihub_run_failed_a.number in body
    assert "PARTNER_TIMEOUT" in body
    assert integrationapihub_run_failed_a.error_message in body
    assert integrationapihub_run_failed_a.payload_excerpt in body
    assert "Retry (Requeue)" in body


def test_integrationapihub_run_retry_sets_pending_backoff_attempt_and_audit(
    client_a, integrationapihub_run_failed_a,
):
    before = timezone.now()
    run_count = ProjectSyncRun.objects.count()
    response = _integrationapihub_post(
        client_a, "syr_retry", integrationapihub_run_failed_a.pk,
    )
    after = timezone.now()
    assert response.status_code == 302
    assert response.url == _integrationapihub_url("syr_detail", integrationapihub_run_failed_a.pk)
    integrationapihub_run_failed_a.refresh_from_db()
    assert integrationapihub_run_failed_a.status == "pending"
    assert integrationapihub_run_failed_a.attempt_no == 2
    delay = SYNC_BACKOFF_SECONDS[min(2, len(SYNC_BACKOFF_SECONDS) - 1)]
    assert integrationapihub_run_failed_a.next_retry_at >= before + timedelta(seconds=delay)
    assert integrationapihub_run_failed_a.next_retry_at <= after + timedelta(seconds=delay)
    assert ProjectSyncRun.objects.count() == run_count
    audits = _integrationapihub_audits(ProjectSyncRun, integrationapihub_run_failed_a.pk, "retry")
    assert audits[-1].changes == {"attempt_no": 2}
    assert any("requeued (attempt 2)" in message for message in _integrationapihub_messages(response))


def test_integrationapihub_monitor_renders_context_content_and_tenant_scope(
    client_a,
    integrationapihub_connector_b,
    integrationapihub_job_a,
    integrationapihub_job_b,
    integrationapihub_run_a,
    integrationapihub_run_failed_a,
    integrationapihub_run_b,
):
    response = _integrationapihub_get(client_a, "sync_monitor")
    assert response.status_code == 200
    expected = {
        "runs", "page_obj", "jobs", "connectors", "status_choices", "stats", "q", "job_id",
        "connector_id", "status", "trigger_source", "date_from", "date_to",
    }
    assert expected <= set(response.context.keys())
    assert set(response.context["stats"]) == {
        "total", "failed", "success", "simulated", "failed_today",
    }
    assert response.context["stats"] == {
        "total": 2,
        "failed": 1,
        "success": 0,
        "simulated": 1,
        "failed_today": 1,
    }
    run_ids = set(_integrationapihub_pks(response, "runs"))
    assert {integrationapihub_run_a.pk, integrationapihub_run_failed_a.pk} <= run_ids
    assert integrationapihub_run_b.pk not in run_ids
    assert integrationapihub_connector_b.pk not in set(
        response.context["connectors"].values_list("pk", flat=True),
    )
    assert integrationapihub_job_b.pk not in set(
        response.context["jobs"].values_list("pk", flat=True),
    )
    body = _integrationapihub_body(response)
    assert "Sync Monitor" in body
    assert integrationapihub_run_a.number in body
    assert integrationapihub_job_b.name not in body
    assert integrationapihub_connector_b.name not in body


def test_integrationapihub_integration_hub_renders_aggregates_domains_and_tenant_scope(
    client_a,
    tenant_a,
    integrationapihub_connector_a,
    integrationapihub_connector_workspace_a,
    integrationapihub_connector_b,
    integrationapihub_mapping_a,
    integrationapihub_job_a,
    integrationapihub_run_a,
    integrationapihub_run_failed_a,
    integrationapihub_run_b,
    integrationapihub_project_a,
    integrationapihub_project_b,
):
    response = _integrationapihub_get(client_a, "integration_hub")
    assert response.status_code == 200
    assert {"stats", "domains", "connectors", "recent_runs", "projects"} <= set(
        response.context.keys(),
    )
    assert set(response.context["stats"]) == {
        "connectors_total", "by_domain", "by_status", "runs_today", "failed_today",
        "jobs_active", "mappings_total", "credentials_due",
    }
    assert response.context["stats"]["connectors_total"] == 2
    assert response.context["stats"]["by_domain"] == {"erp": 1, "storage": 1}
    assert response.context["stats"]["by_status"] == {"connected": 1, "disconnected": 1}
    assert response.context["stats"]["runs_today"] == 2
    assert response.context["stats"]["failed_today"] == 1
    assert response.context["stats"]["jobs_active"] == 1
    assert response.context["stats"]["mappings_total"] == 1
    assert response.context["stats"]["credentials_due"] == 1
    assert len(response.context["domains"]) == len(ProjectIntegrationConnector.DOMAIN_CHOICES)
    erp = next(row for row in response.context["domains"] if row["value"] == "erp")
    storage = next(row for row in response.context["domains"] if row["value"] == "storage")
    assert erp == {"value": "erp", "label": "ERP & Finance", "total": 1, "connected": 1, "failing": 0}
    assert storage == {
        "value": "storage", "label": "File Storage", "total": 1, "connected": 0, "failing": 0,
    }
    connector_ids = set(response.context["connectors"].values_list("pk", flat=True))
    assert connector_ids == {
        integrationapihub_connector_a.pk,
        integrationapihub_connector_workspace_a.pk,
    }
    assert integrationapihub_connector_b.pk not in connector_ids
    run_ids = set(response.context["recent_runs"].values_list("pk", flat=True))
    assert {integrationapihub_run_a.pk, integrationapihub_run_failed_a.pk} <= run_ids
    assert integrationapihub_run_b.pk not in run_ids
    project_ids = set(response.context["projects"].values_list("pk", flat=True))
    assert integrationapihub_project_a.pk in project_ids
    assert integrationapihub_project_b.pk not in project_ids
    body = _integrationapihub_body(response)
    assert "Integration & API Hub" in body
    assert integrationapihub_connector_a.number in body
    assert integrationapihub_connector_workspace_a.number in body
    assert integrationapihub_connector_b.name not in body


def test_integrationapihub_integration_hub_query_cost_is_flat_across_all_domains(
    client_a,
    tenant_a,
    django_assert_max_num_queries,
):
    _integrationapihub_connector(
        tenant_a, project=None, name="Hub budget ERP", domain="erp",
    )
    _integrationapihub_get(client_a, "integration_hub")
    baseline, _ = _integrationapihub_measure(client_a, "integration_hub")
    for domain in ("crm", "hris", "devops", "storage", "custom"):
        _integrationapihub_connector(
            tenant_a,
            project=None,
            name=f"Hub budget {domain}",
            domain=domain,
        )
    with django_assert_max_num_queries(baseline):
        response = _integrationapihub_get(client_a, "integration_hub")
    assert response.status_code == 200
    assert len(response.context["connectors"]) == 6
    assert response.context["stats"]["connectors_total"] == 6
    assert sum(row["total"] for row in response.context["domains"]) == 6


@pytest.mark.parametrize("route", ["syr_list", "sync_monitor"])
def test_integrationapihub_run_registers_render_connector_filter_select(
    client_a, integrationapihub_connector_a, route,
):
    response = _integrationapihub_get(
        client_a, route, connector=str(integrationapihub_connector_a.pk),
    )
    assert response.status_code == 200
    assert response.context["connector_id"] == str(integrationapihub_connector_a.pk)
    assert 'name="connector"' in _integrationapihub_body(response)
    assert 'id="id_connector"' in _integrationapihub_body(response)


def test_integrationapihub_monitor_supplies_and_renders_trigger_filter(
    client_a, integrationapihub_job_a,
):
    response = _integrationapihub_get(
        client_a, "sync_monitor", trigger_source="manual",
    )
    assert response.status_code == 200
    assert response.context["trigger_choices"] == ProjectSyncRun.TRIGGER_SOURCE_CHOICES
    assert response.context["trigger_source"] == "manual"
    assert 'name="trigger_source"' in _integrationapihub_body(response)
    assert 'id="id_trigger_source"' in _integrationapihub_body(response)


@pytest.mark.parametrize(
    "route,empty_key",
    [
        ("ixc_list", "connectors"),
        ("ixm_list", "mappings"),
        ("syj_list", "jobs"),
        ("syr_list", "runs"),
        ("sync_monitor", "runs"),
    ],
)
def test_integrationapihub_tenantless_read_pages_are_empty(
    projectinitiation_tenantless_client,
    integrationapihub_connector_a,
    integrationapihub_mapping_a,
    integrationapihub_job_a,
    integrationapihub_run_a,
    route,
    empty_key,
):
    response = _integrationapihub_get(projectinitiation_tenantless_client, route)
    assert response.status_code == 200
    assert list(response.context[empty_key]) == []
    body = _integrationapihub_body(response)
    assert integrationapihub_connector_a.name not in body
    assert integrationapihub_job_a.name not in body
    assert integrationapihub_run_a.number not in body


def test_integrationapihub_tenantless_hub_and_monitor_aggregates_are_zero(
    projectinitiation_tenantless_client,
    integrationapihub_connector_a,
    integrationapihub_mapping_a,
    integrationapihub_job_a,
    integrationapihub_run_failed_a,
):
    hub = _integrationapihub_get(projectinitiation_tenantless_client, "integration_hub")
    monitor = _integrationapihub_get(projectinitiation_tenantless_client, "sync_monitor")
    assert hub.status_code == 200
    assert monitor.status_code == 200
    assert hub.context["stats"]["connectors_total"] == 0
    assert hub.context["stats"]["mappings_total"] == 0
    assert hub.context["stats"]["jobs_active"] == 0
    assert list(hub.context["connectors"]) == []
    assert list(hub.context["recent_runs"]) == []
    assert monitor.context["stats"] == {
        "total": 0,
        "failed": 0,
        "success": 0,
        "simulated": 0,
        "failed_today": 0,
    }
    assert list(monitor.context["runs"]) == []


@pytest.mark.parametrize("route", ["ixc_create", "ixm_create", "syj_create"])
def test_integrationapihub_tenantless_create_get_redirects_before_rendering_a_form(
    projectinitiation_tenantless_client,
    route,
):
    response = _integrationapihub_get(projectinitiation_tenantless_client, route)
    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")


@pytest.mark.parametrize("route,fixture_name", _INTEGRATIONAPIHUB_POST_ONLY)
def test_integrationapihub_every_mutating_route_rejects_get(
    client_a,
    request,
    route,
    fixture_name,
):
    obj = request.getfixturevalue(fixture_name)
    response = _integrationapihub_get(client_a, route, obj.pk)
    assert response.status_code == 405
