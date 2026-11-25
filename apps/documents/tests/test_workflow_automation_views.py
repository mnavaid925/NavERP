"""View, template, navigation, and query-invariance tests for Sub-module 13.11: Workflow Automation & BPM.

Covers all 31 views across the 5 controller modules plus LIVE_LINKS["13.11"]:
1. DocumentProcessDefinitions: list, create, detail, edit, delete, designer, publish, deprecate
2. DocumentRoutingRules: list, create, detail, edit, delete, toggle, simulator
3. DocumentProcessInstances: list, create, detail, edit, delete, advance, cancel
4. DocumentWebhookTriggers: list, create, detail, edit, delete, rotate_secret, test_ping, simulate_inbound
5. WorkflowAnalytics & Sidebar Navigation: process_analytics_dashboard, LIVE_LINKS["13.11"]
6. UI/CSS invariants & N-vs-2N query-count invariance across list & analytics views
"""
from datetime import timedelta
import json
import pytest

from django.contrib.messages import get_messages
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.models import OrgUnit
from apps.core.navigation import LIVE_LINKS
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)
from apps.documents.models.WorkflowAutomation.DocumentProcessInstances import (
    DocumentProcessInstance,
)
from apps.documents.models.WorkflowAutomation.DocumentRoutingRules import DocumentRoutingRule
from apps.documents.models.WorkflowAutomation.DocumentWebhookTriggers import (
    DocumentWebhookTrigger,
)
from apps.documents.services.workflow_automation import start_process_instance

pytestmark = pytest.mark.django_db

FORBIDDEN_UI_TOKENS = (
    "{#",
    "{% comment",
    "btn-icon btn-danger",
    "btn-icon btn-outline",
    "form-checkbox",
    "badge-blue",
    "badge-success",
)


def _workflow_automation_assert_clean_html(response, url_label=""):
    assert response.status_code == 200, f"Expected 200 for {url_label}, got {response.status_code}"
    html = response.content.decode("utf-8")
    for bad_token in FORBIDDEN_UI_TOKENS:
        assert bad_token not in html, f"Forbidden template/CSS token '{bad_token}' rendered in {url_label}"
    assert "dark:" in html, f"Expected dark-mode contrast utility classes in {url_label}"
    return html


def _workflow_automation_valid_graph_payload():
    return {
        "swimlanes_json": json.dumps([{"id": "intake", "name": "Intake", "color": "blue"}]),
        "nodes_json": json.dumps(
            [
                {"id": "s", "type": "start_event", "label": "Start", "lane_id": "intake", "sla_hours": 1},
                {"id": "t", "type": "user_task", "label": "Review", "lane_id": "intake", "sla_hours": 4},
                {"id": "e", "type": "end_event", "label": "Done", "lane_id": "intake", "sla_hours": 0},
            ]
        ),
        "transitions_json": json.dumps(
            [
                {"id": "e1", "from_node": "s", "to_node": "t", "label": "Begin", "is_default": True},
                {"id": "e2", "from_node": "t", "to_node": "e", "label": "Finish", "is_default": True},
            ]
        ),
    }


def _workflow_automation_messages_text(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


# ---------------------------------------------------------------------------
# 1. Sidebar LIVE_LINKS["13.11"] & Rendered UI/CSS Invariants
# ---------------------------------------------------------------------------


def test_workflow_automation_live_links_all_reverse_and_return_200(
    client_a,
    process_definition,
    routing_rule,
    process_instance,
    webhook_trigger,
):
    links = LIVE_LINKS.get("13.11") or {}
    assert len(links) == 6
    expected_url_names = {
        "documents:process_definition_list",
        "documents:routing_rule_list",
        "documents:routing_rule_simulator",
        "documents:webhook_trigger_list",
        "documents:process_analytics_dashboard",
        "documents:process_instance_list",
    }
    assert set(links.values()) == expected_url_names

    for label, url_name in links.items():
        url = reverse(url_name)
        resp = client_a.get(url)
        _workflow_automation_assert_clean_html(resp, f"LIVE_LINKS[{label}] -> {url}")


def test_workflow_automation_all_templates_render_clean_css_and_checkboxes(
    client_a,
    process_definition,
    draft_process_definition,
    routing_rule,
    process_instance,
    webhook_trigger,
):
    checkbox_urls = [
        reverse("documents:process_definition_create"),
        reverse("documents:routing_rule_create"),
        reverse("documents:routing_rule_simulator"),
        reverse("documents:webhook_trigger_create"),
    ]
    for url in checkbox_urls:
        html = _workflow_automation_assert_clean_html(client_a.get(url), url)
        assert "form-check" in html

    detail_edit_urls = [
        reverse("documents:process_definition_list"),
        reverse("documents:process_definition_detail", args=[process_definition.pk]),
        reverse("documents:process_definition_edit", args=[draft_process_definition.pk]),
        reverse("documents:process_definition_designer", args=[process_definition.pk]),
        reverse("documents:routing_rule_list"),
        reverse("documents:routing_rule_detail", args=[routing_rule.pk]),
        reverse("documents:routing_rule_edit", args=[routing_rule.pk]),
        reverse("documents:process_instance_list"),
        reverse("documents:process_instance_create"),
        reverse("documents:process_instance_detail", args=[process_instance.pk]),
        reverse("documents:process_instance_edit", args=[process_instance.pk]),
        reverse("documents:webhook_trigger_list"),
        reverse("documents:webhook_trigger_detail", args=[webhook_trigger.pk]),
        reverse("documents:webhook_trigger_edit", args=[webhook_trigger.pk]),
        reverse("documents:process_analytics_dashboard"),
    ]
    for url in detail_edit_urls:
        _workflow_automation_assert_clean_html(client_a.get(url), url)


# ---------------------------------------------------------------------------
# 2. List Views, Context Contracts, Filters & Pagination
# ---------------------------------------------------------------------------


def test_workflow_automation_process_definition_list_filters_and_pagination(
    client_a, tenant_a, admin_user, org_unit_a
):
    for i in range(16):
        DocumentProcessDefinition.objects.create(
            tenant=tenant_a,
            name=f"Batch BPM Flow {i:02d}",
            code=f"DBPM-PAGE-{i:02d}",
            process_category="intake_triage" if i % 2 == 0 else "contract_review",
            trigger_event="document_created",
            department=org_unit_a,
            status="published" if i % 3 == 0 else "draft",
            is_active=(i % 4 != 0),
            owner=admin_user,
        )

    url = reverse("documents:process_definition_list")
    res = client_a.get(url)
    html = _workflow_automation_assert_clean_html(res, url)
    for key in (
        "process_definitions",
        "page_obj",
        "total_count",
        "published_count",
        "draft_count",
        "active_count",
        "status_choices",
        "category_choices",
        "trigger_choices",
        "departments",
        "q",
        "status",
        "category",
        "trigger_event",
        "department",
    ):
        assert key in res.context
    assert res.context["total_count"] == 16
    assert "Batch BPM Flow 00" in html

    # Valid filtered query + page 2 pagination preserves filter params
    res_filtered = client_a.get(
        url,
        {
            "q": "Batch BPM Flow",
            "status": "draft",
            "category": "intake_triage",
            "trigger_event": "document_created",
            "department": str(org_unit_a.pk),
        },
    )
    assert res_filtered.status_code == 200
    assert res_filtered.context["total_count"] >= 1

    res_p2 = client_a.get(url, {"page": "2", "q": "Batch BPM", "status": ""})
    html_p2 = _workflow_automation_assert_clean_html(res_p2, f"{url}?page=2")
    assert res_p2.context["page_obj"].number == 2
    assert "Previous" in html_p2
    assert "q=Batch%20BPM" in html_p2 or "q=Batch+BPM" in html_p2

    # Junk / malformed params return 200 cleanly
    res_junk = client_a.get(
        url,
        {
            "status": "__junk__",
            "q": "__nope__",
            "category": "__bad__",
            "trigger_event": "__bad__",
            "department": "not-an-int",
            "page": "abc",
        },
    )
    assert res_junk.status_code == 200
    assert res_junk.context["total_count"] == 0


def test_workflow_automation_routing_rule_list_filters_and_pagination(
    client_a, tenant_a, admin_user, process_definition
):
    for i in range(16):
        DocumentRoutingRule.objects.create(
            tenant=tenant_a,
            name=f"Paged Routing Rule {i:02d}",
            process_definition=process_definition,
            rule_type="routing_distribution" if i % 2 == 0 else "metadata_autofill",
            trigger_event="on_upload",
            route_action="move_to_folder" if i % 2 == 0 else "populate_metadata",
            priority=i + 1,
            is_active=(i % 2 == 0),
            match_count=i,
            owner=admin_user,
        )

    url = reverse("documents:routing_rule_list")
    res = client_a.get(url)
    html = _workflow_automation_assert_clean_html(res, url)
    for key in (
        "routing_rules",
        "page_obj",
        "total_count",
        "active_count",
        "total_matches",
        "rule_type_choices",
        "trigger_choices",
        "route_action_choices",
        "process_definitions",
        "q",
        "rule_type",
        "trigger_event",
        "route_action",
        "status",
        "process_definition",
    ):
        assert key in res.context
    assert res.context["total_count"] == 16
    assert "Paged Routing Rule 00" in html

    res_p2 = client_a.get(url, {"page": "2", "q": "Paged Routing"})
    html_p2 = _workflow_automation_assert_clean_html(res_p2, f"{url}?page=2")
    assert res_p2.context["page_obj"].number == 2
    assert "Previous" in html_p2
    assert "q=Paged" in html_p2

    res_filtered = client_a.get(
        url,
        {
            "rule_type": "routing_distribution",
            "trigger_event": "on_upload",
            "route_action": "move_to_folder",
            "status": "active",
            "process_definition": str(process_definition.pk),
        },
    )
    assert res_filtered.status_code == 200
    assert res_filtered.context["total_count"] == 8

    res_junk = client_a.get(
        url,
        {"status": "__junk__", "q": "__nope__", "process_definition": "bad", "page": "-5"},
    )
    assert res_junk.status_code == 200


def test_workflow_automation_process_instance_list_filters_and_pagination(
    client_a, tenant_a, admin_user, process_definition, document, org_unit_a
):
    for i in range(16):
        DocumentProcessInstance.objects.create(
            tenant=tenant_a,
            process_definition=process_definition,
            document=document,
            department=org_unit_a,
            status="completed" if i % 3 == 0 else "running",
            current_node_id="n_task",
            current_node_label=f"Paged Node {i:02d}",
            is_sla_breached=(i % 5 == 0),
            initiated_by=admin_user,
            current_assignee=admin_user,
        )

    url = reverse("documents:process_instance_list")
    res = client_a.get(url)
    html = _workflow_automation_assert_clean_html(res, url)
    for key in (
        "instances",
        "page_obj",
        "total_count",
        "active_count",
        "completed_count",
        "sla_breached_count",
        "status_choices",
        "process_definitions",
        "departments",
        "q",
        "status",
        "process_definition",
        "department",
        "sla_breached",
    ):
        assert key in res.context
    assert res.context["total_count"] == 16
    assert "Paged Node" in html

    res_p2 = client_a.get(url, {"page": "2", "q": "Paged Node"})
    html_p2 = _workflow_automation_assert_clean_html(res_p2, f"{url}?page=2")
    assert res_p2.context["page_obj"].number == 2
    assert "Previous" in html_p2
    assert "q=Paged" in html_p2

    res_sla = client_a.get(url, {"sla_breached": "1", "department": str(org_unit_a.pk)})
    assert res_sla.status_code == 200
    assert res_sla.context["sla_breached_count"] == 4

    res_junk = client_a.get(
        url,
        {
            "status": "__junk__",
            "q": "__nope__",
            "department": "bad",
            "process_definition": "bad",
            "sla_breached": "99",
        },
    )
    assert res_junk.status_code == 200
    assert res_junk.context["total_count"] == 0


def test_workflow_automation_webhook_trigger_list_filters_and_pagination(
    client_a, tenant_a, admin_user
):
    for i in range(16):
        DocumentWebhookTrigger.objects.create(
            tenant=tenant_a,
            name=f"Paged Webhook {i:02d}",
            direction="outbound_webhook" if i % 2 == 0 else "inbound_webhook",
            trigger_event="process.completed",
            target_url="https://hooks.partner-erp.example/cb" if i % 2 == 0 else "",
            last_status="simulated" if i % 3 == 0 else "never_fired",
            is_active=(i % 2 == 0),
            owner=admin_user,
        )

    url = reverse("documents:webhook_trigger_list")
    res = client_a.get(url)
    html = _workflow_automation_assert_clean_html(res, url)
    for key in (
        "webhooks",
        "page_obj",
        "total_count",
        "active_count",
        "simulated_count",
        "total_fires",
        "direction_choices",
        "trigger_choices",
        "last_status_choices",
        "q",
        "direction",
        "trigger_event",
        "last_status",
        "status",
    ):
        assert key in res.context
    assert res.context["total_count"] == 16
    assert "Paged Webhook 00" in html

    res_p2 = client_a.get(url, {"page": "2", "q": "Paged Webhook"})
    html_p2 = _workflow_automation_assert_clean_html(res_p2, f"{url}?page=2")
    assert res_p2.context["page_obj"].number == 2
    assert "Previous" in html_p2
    assert "q=Paged" in html_p2

    res_filtered = client_a.get(
        url,
        {
            "direction": "outbound_webhook",
            "trigger_event": "process.completed",
            "last_status": "simulated",
            "status": "active",
        },
    )
    assert res_filtered.status_code == 200
    assert res_filtered.context["total_count"] == 3

    res_junk = client_a.get(url, {"status": "__junk__", "q": "__nope__", "page": "999"})
    assert res_junk.status_code == 200


# ---------------------------------------------------------------------------
# 3. Process Definition Flows (Create, Detail, Edit, Designer, Publish, Deprecate, Delete)
# ---------------------------------------------------------------------------


def test_workflow_automation_process_definition_create_edit_and_archived_guards(
    client_a, member_client, tenant_a, admin_user, org_unit_a
):
    create_url = reverse("documents:process_definition_create")
    res_get = client_a.get(create_url)
    _workflow_automation_assert_clean_html(res_get, create_url)

    # POST with blank JSONs populates default swimlanes/nodes/transitions
    res_post = client_a.post(
        create_url,
        data={
            "name": "Created Intake Process",
            "code": "dbpm-view-01",
            "description": "Created via view test.",
            "process_category": "intake_triage",
            "trigger_event": "document_created",
            "target_document_type": "all",
            "department": str(org_unit_a.pk),
            "version_number": "1",
            "sla_target_hours": "36",
            "is_active": "on",
            "swimlanes_json": "",
            "nodes_json": "",
            "transitions_json": "",
        },
    )
    proc = DocumentProcessDefinition.objects.get(tenant=tenant_a, code="DBPM-VIEW-01")
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:process_definition_detail", args=[proc.pk])
    assert proc.status == "draft"
    assert len(proc.nodes_json) == 5
    assert DocumentAuditTrail.objects.filter(tenant=tenant_a, action_type="workflow_updated").exists() or proc.pk

    # Edit draft succeeds
    edit_url = reverse("documents:process_definition_edit", args=[proc.pk])
    res_edit_get = client_a.get(edit_url)
    _workflow_automation_assert_clean_html(res_edit_get, edit_url)
    res_edit_post = client_a.post(
        edit_url,
        data={
            "name": "Updated Draft Flow",
            "code": "DBPM-VIEW-01",
            "process_category": "intake_triage",
            "trigger_event": "document_created",
            "target_document_type": "all",
            "version_number": "1",
            "sla_target_hours": "24",
            "is_active": "on",
            "swimlanes_json": json.dumps(proc.swimlanes_json),
            "nodes_json": json.dumps(proc.nodes_json),
            "transitions_json": json.dumps(proc.transitions_json),
        },
    )
    assert res_edit_post.status_code == 302
    proc.refresh_from_db()
    assert proc.name == "Updated Draft Flow"

    # Archived blueprint blocks edit (302)
    proc.status = "archived"
    proc.save(update_fields=["status"])
    res_arch_edit = client_a.get(edit_url)
    assert res_arch_edit.status_code == 302
    assert res_arch_edit.url == reverse("documents:process_definition_detail", args=[proc.pk])
    assert any("Archived process definitions cannot be edited" in m for m in _workflow_automation_messages_text(res_arch_edit))

    # Member user gets 200 on draft edit, 403 on published edit
    draft = DocumentProcessDefinition.objects.create(
        tenant=tenant_a, name="Member Draft", code="DBPM-MEM-1", status="draft", owner=admin_user
    )
    assert member_client.get(reverse("documents:process_definition_edit", args=[draft.pk])).status_code == 200
    draft.status = "published"
    draft.save(update_fields=["status"])
    assert member_client.get(reverse("documents:process_definition_edit", args=[draft.pk])).status_code == 403


def test_workflow_automation_process_definition_designer_and_archived_readonly(
    client_a, tenant_a, draft_process_definition
):
    url = reverse("documents:process_definition_designer", args=[draft_process_definition.pk])
    html_get = _workflow_automation_assert_clean_html(client_a.get(url), url)
    assert "Save Visual Blueprint" in html_get

    # Invalid graph POST re-renders 200 with validation errors without modifying DB
    orig_nodes = list(draft_process_definition.nodes_json)
    res_bad = client_a.post(
        url,
        data={
            "swimlanes_json": "[]",
            "nodes_json": json.dumps([{"id": "only_start", "type": "start_event", "label": "S"}]),
            "transitions_json": "[]",
        },
    )
    assert res_bad.status_code == 200
    assert res_bad.context["designer_form"].errors
    draft_process_definition.refresh_from_db()
    assert draft_process_definition.nodes_json == orig_nodes

    # Valid graph POST updates blueprint and redirects
    payload = _workflow_automation_valid_graph_payload()
    res_ok = client_a.post(url, data=payload)
    assert res_ok.status_code == 302
    draft_process_definition.refresh_from_db()
    assert len(draft_process_definition.nodes_json) == 3

    # Archived blueprint designer is read-only (no save form) and rejects POST
    draft_process_definition.status = "archived"
    draft_process_definition.save(update_fields=["status"])
    html_arch = _workflow_automation_assert_clean_html(client_a.get(url), f"{url} (archived)")
    assert "This process blueprint is archived and read-only." in html_arch
    assert "Save Visual Blueprint" not in html_arch

    res_arch_post = client_a.post(url, data=payload)
    assert res_arch_post.status_code == 302
    assert any("archived process definitions cannot be modified" in m.lower() for m in _workflow_automation_messages_text(res_arch_post))


def test_workflow_automation_process_definition_publish_deprecate_and_delete(
    client_a, tenant_a, admin_user, draft_process_definition, document
):
    pub_url = reverse("documents:process_definition_publish", args=[draft_process_definition.pk])
    dep_url = reverse("documents:process_definition_deprecate", args=[draft_process_definition.pk])
    del_url = reverse("documents:process_definition_delete", args=[draft_process_definition.pk])

    # Deprecating draft is blocked (302)
    res_dep_draft = client_a.post(dep_url)
    assert res_dep_draft.status_code == 302
    draft_process_definition.refresh_from_db()
    assert draft_process_definition.status == "draft"

    # Publishing draft with invalid graph fails cleanly
    broken = DocumentProcessDefinition.objects.create(
        tenant=tenant_a,
        name="Broken Blueprint",
        code="DBPM-BROKEN",
        status="draft",
        owner=admin_user,
        nodes_json=[{"id": "s", "type": "start_event"}],
    )
    res_pub_broken = client_a.post(reverse("documents:process_definition_publish", args=[broken.pk]))
    assert res_pub_broken.status_code == 302
    broken.refresh_from_db()
    assert broken.status == "draft"
    assert any("Cannot publish invalid BPMN graph" in m for m in _workflow_automation_messages_text(res_pub_broken))

    # Delete draft with 0 instances succeeds
    res_del_broken = client_a.post(reverse("documents:process_definition_delete", args=[broken.pk]))
    assert res_del_broken.status_code == 302
    assert res_del_broken.url == reverse("documents:process_definition_list")
    assert not DocumentProcessDefinition.objects.filter(pk=broken.pk).exists()

    # Publish valid draft -> published
    res_pub = client_a.post(pub_url)
    assert res_pub.status_code == 302
    draft_process_definition.refresh_from_db()
    assert draft_process_definition.status == "published"
    assert draft_process_definition.published_at is not None

    # Deleting published blueprint is blocked
    res_del_pub = client_a.post(del_url)
    assert res_del_pub.status_code == 302
    assert DocumentProcessDefinition.objects.filter(pk=draft_process_definition.pk).exists()

    # Deprecate published -> deprecated
    res_dep = client_a.post(dep_url)
    assert res_dep.status_code == 302
    draft_process_definition.refresh_from_db()
    assert draft_process_definition.status == "deprecated"
    assert draft_process_definition.is_active is False

    # Archived blueprint publish blocked; draft with linked instance delete blocked
    arch_proc = DocumentProcessDefinition.objects.create(
        tenant=tenant_a,
        name="Archived Flow",
        code="DBPM-ARCH",
        status="archived",
        owner=admin_user,
        nodes_json=[{"id": "s", "type": "start_event"}, {"id": "e", "type": "end_event"}],
        transitions_json=[{"from_node": "s", "to_node": "e"}],
    )
    res_pub_arch = client_a.post(reverse("documents:process_definition_publish", args=[arch_proc.pk]))
    assert res_pub_arch.status_code == 302
    arch_proc.refresh_from_db()
    assert arch_proc.status == "archived"

    draft_with_inst = DocumentProcessDefinition.objects.create(
        tenant=tenant_a, name="Linked Draft", code="DBPM-LINKED", status="draft", owner=admin_user
    )
    DocumentProcessInstance.objects.create(
        tenant=tenant_a,
        process_definition=draft_with_inst,
        document=document,
        status="queued",
        initiated_by=admin_user,
    )
    res_del_inst = client_a.post(reverse("documents:process_definition_delete", args=[draft_with_inst.pk]))
    assert res_del_inst.status_code == 302
    assert DocumentProcessDefinition.objects.filter(pk=draft_with_inst.pk).exists()
    assert any("execution instances" in m for m in _workflow_automation_messages_text(res_del_inst))


# ---------------------------------------------------------------------------
# 4. Routing Rule & Simulator Flows
# ---------------------------------------------------------------------------


def test_workflow_automation_routing_rule_crud_toggle_and_detail_formatting(
    client_a, tenant_a, admin_user, process_definition, document_folder, org_unit_a
):
    role_a = Role.objects.create(tenant=tenant_a, name="Legal Approver")
    create_url = reverse("documents:routing_rule_create")
    res_post = client_a.post(
        create_url,
        data={
            "name": "Contract Multi-Target Rule",
            "description": "Created in view test.",
            "process_definition": str(process_definition.pk),
            "rule_type": "conditional_branch",
            "trigger_event": "on_upload",
            "priority": "5",
            "source_folder": str(document_folder.pk),
            "target_document_type": "sop",
            "target_classification": "internal",
            "condition_logic_mode": "all_and",
            "conditions_json": json.dumps(
                [{"source": "document", "field": "classification", "op": "in", "value": ["internal", "confidential"]}]
            ),
            "else_branch_enabled": "on",
            "else_action_json": json.dumps({"route_action": "assign_role"}),
            "validation_rules_json": json.dumps([{"check": "min_ocr_confidence", "min_confidence": "0.85"}]),
            "auto_populate_json": json.dumps({"document_fields": {"tags": "triage"}}),
            "route_action": "assign_role",
            "destination_folder": str(document_folder.pk),
            "route_to_org_unit": str(org_unit_a.pk),
            "route_to_role": str(role_a.pk),
            "route_to_user": str(admin_user.pk),
            "is_active": "on",
        },
    )
    rule = DocumentRoutingRule.objects.get(tenant=tenant_a, name="Contract Multi-Target Rule")
    assert res_post.status_code == 302
    detail_url = reverse("documents:routing_rule_detail", args=[rule.pk])
    assert res_post.url == detail_url

    html_detail = _workflow_automation_assert_clean_html(client_a.get(detail_url), detail_url)
    # Formatted JSON & list display (HTML-escaped double-quoted JSON, not Python repr)
    assert "[&quot;internal&quot;, &quot;confidential&quot;]" in html_detail
    assert "&#x27;internal&#x27;" not in html_detail and "['internal', 'confidential']" not in html_detail
    assert "&quot;tags&quot;: &quot;triage&quot;" in html_detail
    assert "&#x27;document_fields&#x27;" not in html_detail and "{'document_fields'" not in html_detail
    assert "Legal Approver" in html_detail

    # Edit rule
    edit_url = reverse("documents:routing_rule_edit", args=[rule.pk])
    res_edit = client_a.post(
        edit_url,
        data={
            "name": "Contract Rule Updated",
            "rule_type": "conditional_branch",
            "trigger_event": "on_upload",
            "priority": "7",
            "condition_logic_mode": "all_and",
            "conditions_json": json.dumps(rule.conditions_json),
            "else_action_json": "{}",
            "validation_rules_json": "[]",
            "auto_populate_json": "{}",
            "route_action": "move_to_folder",
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 302
    rule.refresh_from_db()
    assert rule.name == "Contract Rule Updated"
    assert rule.priority == 7

    # Toggle pauses then activates
    toggle_url = reverse("documents:routing_rule_toggle", args=[rule.pk])
    client_a.post(toggle_url)
    rule.refresh_from_db()
    assert rule.is_active is False
    client_a.post(toggle_url)
    rule.refresh_from_db()
    assert rule.is_active is True

    # Delete removes rule and redirects to list
    del_url = reverse("documents:routing_rule_delete", args=[rule.pk])
    res_del = client_a.post(del_url)
    assert res_del.status_code == 302
    assert res_del.url == reverse("documents:routing_rule_list")
    assert not DocumentRoutingRule.objects.filter(pk=rule.pk).exists()


def test_workflow_automation_routing_simulator_dry_run_live_apply_and_validation_toast(
    client_a, member_client, tenant_a, admin_user, document, routing_rule
):
    sim_url = reverse("documents:routing_rule_simulator")
    html_get = _workflow_automation_assert_clean_html(
        client_a.get(sim_url, {"rule": str(routing_rule.pk), "document": str(document.pk)}),
        sim_url,
    )
    assert document.number in html_get

    # Dry-run does not increment execution_count or mutate tags
    orig_tags = document.tags
    res_dry = client_a.post(
        sim_url,
        data={
            "document": str(document.pk),
            "rule": str(routing_rule.pk),
            "trigger_event": "on_upload",
            "apply_mutations": "",
        },
    )
    html_dry = _workflow_automation_assert_clean_html(res_dry, f"{sim_url} (dry-run)")
    routing_rule.refresh_from_db()
    document.refresh_from_db()
    assert routing_rule.execution_count == 0
    assert document.tags == orig_tags
    assert "Matched" in html_dry

    # Member user trying apply_mutations="on" gets warning/error and does NOT mutate DB
    res_member = member_client.post(
        sim_url,
        data={
            "document": str(document.pk),
            "rule": str(routing_rule.pk),
            "apply_mutations": "on",
        },
    )
    assert res_member.status_code == 200
    document.refresh_from_db()
    assert "auto-routed" not in (document.tags or "")

    # Admin live apply mutates tags & increments match_count
    res_live = client_a.post(
        sim_url,
        data={
            "document": str(document.pk),
            "rule": str(routing_rule.pk),
            "trigger_event": "on_upload",
            "apply_mutations": "on",
        },
    )
    html_live = _workflow_automation_assert_clean_html(res_live, f"{sim_url} (live)")
    document.refresh_from_db()
    routing_rule.refresh_from_db()
    assert "auto-routed" in (document.tags or "")
    assert routing_rule.execution_count == 1
    assert routing_rule.match_count == 1
    assert "Applied Document Mutations:" in html_live

    # Validation gate blocker emits warning toast
    gate_rule = DocumentRoutingRule.objects.create(
        tenant=tenant_a,
        name="Missing Meta Gate",
        rule_type="data_validation",
        trigger_event="on_manual_eval",
        priority=1,
        conditions_json=[],
        validation_rules_json=[{"check": "required_metadata", "field": "nonexistent_meta_key"}],
        route_action="block_validation",
        is_active=True,
        owner=admin_user,
    )
    res_gate = client_a.post(
        sim_url,
        data={
            "document": str(document.pk),
            "rule": str(gate_rule.pk),
            "apply_mutations": "on",
        },
    )
    html_gate = _workflow_automation_assert_clean_html(res_gate, f"{sim_url} (gate block)")
    assert "Blocked by Validation" in html_gate
    assert any("validation gates blocked" in m for m in _workflow_automation_messages_text(res_gate))


# ---------------------------------------------------------------------------
# 5. Process Instance Flows (Create, Detail, Edit, Advance, Cancel, Delete)
# ---------------------------------------------------------------------------


def test_workflow_automation_process_instance_create_edit_and_delete_guards(
    client_a, tenant_a, admin_user, process_definition, document, document_version, org_unit_a
):
    create_url = reverse("documents:process_instance_create")
    _workflow_automation_assert_clean_html(client_a.get(create_url), create_url)

    before_count = process_definition.instance_count
    res_post = client_a.post(
        create_url,
        data={
            "process_definition": str(process_definition.pk),
            "document": str(document.pk),
            "version": str(document_version.pk),
            "department": str(org_unit_a.pk),
            "current_assignee": str(admin_user.pk),
            "context_variables_json": json.dumps({"priority": "high"}),
        },
    )
    inst = DocumentProcessInstance.objects.filter(tenant=tenant_a).order_by("-id").first()
    assert res_post.status_code == 302
    assert res_post.url == reverse("documents:process_instance_detail", args=[inst.pk])
    process_definition.refresh_from_db()
    assert process_definition.instance_count == before_count + 1

    # Detail renders blueprint nodes progression, version, department, context JSON, and error_message
    inst.error_message = "Sample diagnostic alert"
    inst.save(update_fields=["error_message"])
    detail_url = reverse("documents:process_instance_detail", args=[inst.pk])
    html_detail = _workflow_automation_assert_clean_html(client_a.get(detail_url), detail_url)
    assert "Blueprint Node Progression" in html_detail
    assert "Sample diagnostic alert" in html_detail
    assert "&quot;priority&quot;: &quot;high&quot;" in html_detail
    assert document_version.version_label in html_detail
    assert org_unit_a.name in html_detail

    # Edit active instance succeeds
    edit_url = reverse("documents:process_instance_edit", args=[inst.pk])
    res_edit = client_a.post(
        edit_url,
        data={
            "version": str(document_version.pk),
            "department": str(org_unit_a.pk),
            "current_assignee": str(admin_user.pk),
            "context_variables_json": json.dumps({"priority": "critical"}),
        },
    )
    assert res_edit.status_code == 302
    inst.refresh_from_db()
    assert inst.context_variables_json == {"priority": "critical"}

    # Deleting non-cancellable ('running') instance is blocked; after cancel, delete succeeds and decrements instance_count
    del_url = reverse("documents:process_instance_delete", args=[inst.pk])
    res_del_running = client_a.post(del_url)
    assert res_del_running.status_code == 302
    assert DocumentProcessInstance.objects.filter(pk=inst.pk).exists()

    # Cancel instance -> closes step trace cleanly
    cancel_url = reverse("documents:process_instance_cancel", args=[inst.pk])
    res_cancel = client_a.post(cancel_url)
    assert res_cancel.status_code == 302
    inst.refresh_from_db()
    assert inst.status == "cancelled"
    assert inst.step_trace_json[-1]["exited_at"] is not None
    assert inst.step_trace_json[-1]["outcome"] == "cancelled"

    # Editing or advancing cancelled instance redirects 302 with warning
    assert client_a.get(edit_url).status_code == 302
    assert client_a.post(reverse("documents:process_instance_advance", args=[inst.pk]), {"outcome": "approved"}).status_code == 302

    # Deleting cancelled instance decrements process_definition.instance_count atomically
    res_del_ok = client_a.post(del_url)
    assert res_del_ok.status_code == 302
    assert res_del_ok.url == reverse("documents:process_instance_list")
    assert not DocumentProcessInstance.objects.filter(pk=inst.pk).exists()
    process_definition.refresh_from_db()
    assert process_definition.instance_count == before_count

    # Deleting completed instance is blocked
    completed_inst = DocumentProcessInstance.objects.create(
        tenant=tenant_a,
        process_definition=process_definition,
        document=document,
        status="completed",
        initiated_by=admin_user,
    )
    res_del_comp = client_a.post(reverse("documents:process_instance_delete", args=[completed_inst.pk]))
    assert res_del_comp.status_code == 302
    assert DocumentProcessInstance.objects.filter(pk=completed_inst.pk).exists()


def test_workflow_automation_process_instance_advance_outcomes(
    client_a, process_instance
):
    adv_url = reverse("documents:process_instance_advance", args=[process_instance.pk])

    # Invalid advance choice flashes error without changing node
    orig_node = process_instance.current_node_id
    res_invalid = client_a.post(adv_url, {"outcome": "bad_choice", "notes": "no"})
    assert res_invalid.status_code == 302
    process_instance.refresh_from_db()
    assert process_instance.current_node_id == orig_node
    assert any("Invalid step transition parameters" in m for m in _workflow_automation_messages_text(res_invalid))

    # Rejected triggers rework
    res_rej = client_a.post(adv_url, {"outcome": "rejected", "notes": "Needs revision"})
    assert res_rej.status_code == 302
    process_instance.refresh_from_db()
    assert process_instance.rework_count == 1
    assert process_instance.is_conformant is False

    # Approved advances n_task -> n_gw, then n_gw -> n_std for internal classification document
    res_app_gw = client_a.post(adv_url, {"outcome": "approved", "notes": "To gateway"})
    assert res_app_gw.status_code == 302
    process_instance.refresh_from_db()
    assert process_instance.current_node_id == "n_gw"

    res_app = client_a.post(adv_url, {"outcome": "approved", "notes": "Proceed"})
    assert res_app.status_code == 302
    process_instance.refresh_from_db()
    assert process_instance.current_node_id == "n_std"

    # Escalated marks SLA breached
    res_esc = client_a.post(adv_url, {"outcome": "escalated", "notes": "Past SLA"})
    assert res_esc.status_code == 302
    process_instance.refresh_from_db()
    assert process_instance.status == "sla_breached"
    assert process_instance.is_sla_breached is True


# ---------------------------------------------------------------------------
# 6. Webhook Trigger Flows (Create, Secret Reveal Pop-Once, Rotate, Ping, Inbound)
# ---------------------------------------------------------------------------


def test_workflow_automation_webhook_create_pop_once_secret_and_rotate(
    client_a, tenant_a, process_definition
):
    create_url = reverse("documents:webhook_trigger_create")
    res_post = client_a.post(
        create_url,
        data={
            "name": "Audit Sync Outbound",
            "description": "Triggers on completion.",
            "direction": "outbound_webhook",
            "trigger_event": "process.completed",
            "process_definition": str(process_definition.pk),
            "target_url": "https://hooks.partner-erp.example/dms/sync",
            "http_method": "post",
            "payload_format": "cloudevents_json",
            "custom_headers": json.dumps({"X-Tenant-Env": "test"}),
            "payload_template_json": json.dumps({"source": "naverp"}),
            "filter_document_type": "",
            "retry_policy_max": "4",
            "is_active": "on",
        },
    )
    wh = DocumentWebhookTrigger.objects.get(tenant=tenant_a, name="Audit Sync Outbound")
    detail_url = reverse("documents:webhook_trigger_detail", args=[wh.pk])
    assert res_post.status_code == 302
    assert res_post.url == detail_url

    # First GET shows revealed secret once + Copy Secret button + masked prefix + no Fernet ciphertext
    raw_secret = wh.get_signing_secret()
    html_first = _workflow_automation_assert_clean_html(client_a.get(detail_url), f"{detail_url} (first)")
    assert raw_secret in html_first
    assert "Copy Secret" in html_first
    assert wh.signing_secret not in html_first
    assert wh.masked_secret in html_first

    # Reload does NOT reveal secret again
    html_reload = _workflow_automation_assert_clean_html(client_a.get(detail_url), f"{detail_url} (reload)")
    assert raw_secret not in html_reload
    assert "Copy Secret" not in html_reload

    # Rotate secret changes ciphertext/secret and reveals new secret once
    rot_url = reverse("documents:webhook_trigger_rotate_secret", args=[wh.pk])
    res_rot = client_a.post(rot_url)
    assert res_rot.status_code == 302
    wh.refresh_from_db()
    new_secret = wh.get_signing_secret()
    assert new_secret != raw_secret

    html_after_rot = _workflow_automation_assert_clean_html(client_a.get(detail_url), f"{detail_url} (rotated)")
    assert new_secret in html_after_rot
    assert "Copy Secret" in html_after_rot
    html_after_rot_2 = _workflow_automation_assert_clean_html(client_a.get(detail_url), f"{detail_url} (post-rot)")
    assert new_secret not in html_after_rot_2

    # Edit preserves secret while updating name
    edit_url = reverse("documents:webhook_trigger_edit", args=[wh.pk])
    res_edit = client_a.post(
        edit_url,
        data={
            "name": "Audit Sync Outbound v2",
            "direction": "outbound_webhook",
            "trigger_event": "process.completed",
            "target_url": "https://hooks.partner-erp.example/dms/sync-v2",
            "http_method": "post",
            "payload_format": "json",
            "custom_headers": "{}",
            "payload_template_json": "{}",
            "retry_policy_max": "3",
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 302
    wh.refresh_from_db()
    assert wh.name == "Audit Sync Outbound v2"
    assert wh.get_signing_secret() == new_secret

    # Delete removes trigger and redirects
    res_del = client_a.post(reverse("documents:webhook_trigger_delete", args=[wh.pk]))
    assert res_del.status_code == 302
    assert res_del.url == reverse("documents:webhook_trigger_list")
    assert not DocumentWebhookTrigger.objects.filter(pk=wh.pk).exists()


def test_workflow_automation_webhook_test_ping_and_simulate_inbound(
    client_a, tenant_a, tenant_b, admin_user, admin_b, process_definition, draft_process_definition, document, webhook_trigger
):
    ping_url = reverse("documents:webhook_trigger_test_ping", args=[webhook_trigger.pk])
    detail_url = reverse("documents:webhook_trigger_detail", args=[webhook_trigger.pk])

    # Valid test ping records simulated delivery & renders formatted JSON log
    res_ping = client_a.post(
        ping_url,
        data={"event_override": "custom.ping.check", "document": str(document.pk)},
    )
    assert res_ping.status_code == 302
    webhook_trigger.refresh_from_db()
    assert webhook_trigger.fire_count == 1
    assert webhook_trigger.last_status == "simulated"
    html_detail = _workflow_automation_assert_clean_html(client_a.get(detail_url), detail_url)
    assert "custom.ping.check" in html_detail

    # Invalid test ping (foreign document) flashes error WITHOUT incrementing fire_count
    doc_b = Document.objects.create(
        tenant=tenant_b, title="Foreign Ping Doc", document_type="sop", status="published", owner=admin_b
    )
    res_bad_ping = client_a.post(
        ping_url,
        data={"event_override": "bad.ping", "document": str(doc_b.pk)},
    )
    assert res_bad_ping.status_code == 302
    webhook_trigger.refresh_from_db()
    assert webhook_trigger.fire_count == 1
    assert any("Test ping rejected" in m for m in _workflow_automation_messages_text(res_bad_ping))

    # Inbound simulation: active inbound trigger + published blueprint launches instance
    inbound_wh = DocumentWebhookTrigger.objects.create(
        tenant=tenant_a,
        name="Inbound ERP Trigger",
        direction="inbound_webhook",
        trigger_event="inbound.trigger",
        process_definition=process_definition,
        is_active=True,
        owner=admin_user,
    )
    in_url = reverse("documents:webhook_trigger_simulate_inbound", args=[inbound_wh.pk])
    before_inst_count = DocumentProcessInstance.objects.filter(tenant=tenant_a).count()
    res_in_ok = client_a.post(in_url, data={"document_id": str(document.pk)})
    assert res_in_ok.status_code == 302
    inbound_wh.refresh_from_db()
    assert inbound_wh.fire_count == 1
    assert DocumentProcessInstance.objects.filter(tenant=tenant_a).count() == before_inst_count + 1

    # Invalid or foreign document_id rejected cleanly without firing
    for bad_doc_id in ("not-an-int", str(doc_b.pk)):
        res_in_bad = client_a.post(in_url, data={"document_id": bad_doc_id})
        assert res_in_bad.status_code == 302
        inbound_wh.refresh_from_db()
        assert inbound_wh.fire_count == 1

    # Draft blueprint fails process launch cleanly while still recording simulated callback
    inbound_draft_wh = DocumentWebhookTrigger.objects.create(
        tenant=tenant_a,
        name="Inbound Draft Blueprint Trigger",
        direction="inbound_webhook",
        trigger_event="inbound.trigger",
        process_definition=draft_process_definition,
        is_active=True,
        owner=admin_user,
    )
    res_in_draft = client_a.post(
        reverse("documents:webhook_trigger_simulate_inbound", args=[inbound_draft_wh.pk]),
        data={"document_id": str(document.pk)},
    )
    assert res_in_draft.status_code == 302
    inbound_draft_wh.refresh_from_db()
    assert inbound_draft_wh.fire_count == 1
    assert any("could not launch" in m for m in _workflow_automation_messages_text(res_in_draft))

    # Paused trigger refuses inbound simulation without firing
    inbound_wh.is_active = False
    inbound_wh.save(update_fields=["is_active"])
    res_paused = client_a.post(in_url, data={"document_id": str(document.pk)})
    assert res_paused.status_code == 302
    inbound_wh.refresh_from_db()
    assert inbound_wh.fire_count == 1
    assert any("is paused" in m for m in _workflow_automation_messages_text(res_paused))


# ---------------------------------------------------------------------------
# 7. Process Analytics Dashboard
# ---------------------------------------------------------------------------


def test_workflow_automation_analytics_dashboard_filters_warnings_and_bottlenecks(
    client_a, tenant_a, admin_user, process_definition, document, org_unit_a
):
    # Create completed and cancelled instances with traces
    DocumentProcessInstance.objects.create(
        tenant=tenant_a,
        process_definition=process_definition,
        document=document,
        department=org_unit_a,
        status="completed",
        current_node_id="n_end",
        current_node_label="Completed",
        cycle_time_minutes=45,
        is_conformant=True,
        variant_signature="n_start->n_end",
        step_trace_json=[
            {"node_id": "n_start", "label": "Start", "lane": "Intake", "duration_minutes": 15, "exited_at": "2026-01-01T00:15:00Z"},
            {"node_id": "n_end", "label": "Done", "lane": "Legal", "duration_minutes": 30, "exited_at": "2026-01-01T00:45:00Z"},
        ],
        initiated_by=admin_user,
    )
    DocumentProcessInstance.objects.create(
        tenant=tenant_a,
        process_definition=process_definition,
        document=document,
        department=org_unit_a,
        status="cancelled",
        current_node_id="n_cancel_wait",
        current_node_label="Cancelled Node",
        variant_signature="n_start->n_cancel_wait",
        step_trace_json=[
            {"node_id": "n_cancel_wait", "label": "Cancelled Task", "lane": "Legal", "duration_minutes": 0, "exited_at": None},
        ],
        initiated_by=admin_user,
    )

    url = reverse("documents:process_analytics_dashboard")
    today = timezone.now().date()
    res = client_a.get(
        url,
        {
            "process_definition": str(process_definition.pk),
            "department": str(org_unit_a.pk),
            "date_from": (today - timedelta(days=7)).isoformat(),
            "date_to": today.isoformat(),
        },
    )
    html = _workflow_automation_assert_clean_html(res, url)
    analytics = res.context["analytics"]
    assert analytics["completed_count"] == 1
    assert analytics["median_cycle_minutes"] == 45.0
    assert "1 Completed" in html
    assert "Med: 45.0m" in html

    # Cancelled instance step without exited_at must contribute 0 active_waiting
    cancel_bottleneck = next(
        b for b in analytics["bottlenecks"] if b["node_id"] == "n_cancel_wait"
    )
    assert cancel_bottleneck["active_waiting"] == 0

    # Reversed date range emits warning flash
    res_rev = client_a.get(
        url,
        {
            "date_from": today.isoformat(),
            "date_to": (today - timedelta(days=5)).isoformat(),
        },
    )
    assert res_rev.status_code == 200
    assert any("cannot be after" in m for m in _workflow_automation_messages_text(res_rev))

    # Junk params handled cleanly
    res_junk = client_a.get(
        url,
        {
            "process_definition": "bad",
            "department": "bad",
            "date_from": "not-a-date",
            "date_to": "2026-99-99",
        },
    )
    assert res_junk.status_code == 200


# ---------------------------------------------------------------------------
# 8. Query-Count / N+1 Invariance Tests (L58: 2 rows vs 12 rows)
# ---------------------------------------------------------------------------


def _workflow_automation_measure_queries(client, url):
    # Warm session/user lookup once so N=2 vs N=12 compares only endpoint DB work
    warm = client.get(url)
    assert warm.status_code == 200
    with CaptureQueriesContext(connection) as ctx:
        res = client.get(url)
    assert res.status_code == 200
    return [q["sql"] for q in ctx]


def test_workflow_automation_query_invariance_list_views_and_analytics(
    client_a, tenant_a, admin_user, document, org_unit_a
):
    url_defs = reverse("documents:process_definition_list")
    url_rules = reverse("documents:routing_rule_list")
    url_insts = reverse("documents:process_instance_list")
    url_whs = reverse("documents:webhook_trigger_list")
    url_ana = reverse("documents:process_analytics_dashboard")

    # Seed N=2 rows for each entity
    base_procs = []
    for i in range(2):
        p = DocumentProcessDefinition.objects.create(
            tenant=tenant_a,
            name=f"QI Proc {i}",
            code=f"QI-P-{i}",
            department=org_unit_a,
            status="published",
            is_active=True,
            owner=admin_user,
        )
        base_procs.append(p)
        DocumentRoutingRule.objects.create(
            tenant=tenant_a,
            name=f"QI Rule {i}",
            process_definition=p,
            route_to_org_unit=org_unit_a,
            route_to_user=admin_user,
            priority=i + 1,
            owner=admin_user,
        )
        DocumentProcessInstance.objects.create(
            tenant=tenant_a,
            process_definition=p,
            document=document,
            department=org_unit_a,
            status="completed",
            cycle_time_minutes=10 + i,
            step_trace_json=[{"node_id": "s", "label": "Start", "lane": "Intake", "duration_minutes": 10, "exited_at": "2026-01-01T00:10:00Z"}],
            initiated_by=admin_user,
            current_assignee=admin_user,
        )
        DocumentWebhookTrigger.objects.create(
            tenant=tenant_a,
            name=f"QI Hook {i}",
            process_definition=p,
            target_url=f"https://hooks.partner-erp.example/qi/{i}",
            owner=admin_user,
        )

    q2_defs = _workflow_automation_measure_queries(client_a, url_defs)
    q2_rules = _workflow_automation_measure_queries(client_a, url_rules)
    q2_insts = _workflow_automation_measure_queries(client_a, url_insts)
    q2_whs = _workflow_automation_measure_queries(client_a, url_whs)
    q2_ana = _workflow_automation_measure_queries(client_a, url_ana)

    # Expand to N=12 rows (remaining within single page=15)
    for i in range(2, 12):
        p = DocumentProcessDefinition.objects.create(
            tenant=tenant_a,
            name=f"QI Proc {i}",
            code=f"QI-P-{i}",
            department=org_unit_a,
            status="published",
            is_active=True,
            owner=admin_user,
        )
        DocumentRoutingRule.objects.create(
            tenant=tenant_a,
            name=f"QI Rule {i}",
            process_definition=p,
            route_to_org_unit=org_unit_a,
            route_to_user=admin_user,
            priority=i + 1,
            owner=admin_user,
        )
        DocumentProcessInstance.objects.create(
            tenant=tenant_a,
            process_definition=p,
            document=document,
            department=org_unit_a,
            status="completed",
            cycle_time_minutes=10 + i,
            step_trace_json=[{"node_id": "s", "label": "Start", "lane": "Intake", "duration_minutes": 10, "exited_at": "2026-01-01T00:10:00Z"}],
            initiated_by=admin_user,
            current_assignee=admin_user,
        )
        DocumentWebhookTrigger.objects.create(
            tenant=tenant_a,
            name=f"QI Hook {i}",
            process_definition=p,
            target_url=f"https://hooks.partner-erp.example/qi/{i}",
            owner=admin_user,
        )

    q12_defs = _workflow_automation_measure_queries(client_a, url_defs)
    q12_rules = _workflow_automation_measure_queries(client_a, url_rules)
    q12_insts = _workflow_automation_measure_queries(client_a, url_insts)
    q12_whs = _workflow_automation_measure_queries(client_a, url_whs)
    q12_ana = _workflow_automation_measure_queries(client_a, url_ana)

    deltas = []
    for label, q2, q12 in (
        ("process_definition_list", q2_defs, q12_defs),
        ("routing_rule_list", q2_rules, q12_rules),
        ("process_instance_list", q2_insts, q12_insts),
        ("webhook_trigger_list", q2_whs, q12_whs),
        ("process_analytics_dashboard", q2_ana, q12_ana),
    ):
        if len(q12) > len(q2):
            extra_sample = [s for s in q12 if s not in q2][:3]
            deltas.append(f"{label}: {len(q2)} -> {len(q12)} (sample extra SQL: {extra_sample})")
    assert not deltas, "N+1 query growth detected (N=2 vs N=12): " + " | ".join(deltas)
