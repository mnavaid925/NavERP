"""Form and validation unit tests for Sub-module 13.11: Workflow Automation & BPM.

Covers all forms in apps/documents/forms/WorkflowAutomation/:
1. DocumentProcessDefinitionForm & ProcessDesignerForm
2. DocumentRoutingRuleForm & RoutingRuleSimulatorForm
3. DocumentProcessInstanceForm & ProcessAdvanceForm
4. DocumentWebhookTriggerForm & WebhookTestPingForm
"""
import json
import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Role
from apps.core.models import BusinessRule, ConnectorDefinition, OrgUnit, WorkflowDefinition
from apps.documents.forms._common import reject_foreign
from apps.documents.forms.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinitionForm,
    ProcessDesignerForm,
)
from apps.documents.forms.WorkflowAutomation.DocumentProcessInstances import (
    DocumentProcessInstanceForm,
    ProcessAdvanceForm,
)
from apps.documents.forms.WorkflowAutomation.DocumentRoutingRules import (
    DocumentRoutingRuleForm,
    RoutingRuleSimulatorForm,
)
from apps.documents.forms.WorkflowAutomation.DocumentWebhookTriggers import (
    DocumentWebhookTriggerForm,
    WebhookTestPingForm,
)
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)

pytestmark = pytest.mark.django_db

FORBIDDEN_SYSTEM_FIELDS = (
    "tenant",
    "number",
    "owner",
    "status",
    "instance_count",
    "published_at",
    "execution_count",
    "match_count",
    "last_evaluated_at",
    "signing_secret",
    "signing_secret_prefix",
    "last_status",
    "last_fired_at",
    "fire_count",
    "failure_count",
    "delivery_history_json",
    "step_trace_json",
    "started_at",
    "due_at",
    "completed_at",
    "cycle_time_minutes",
    "rework_count",
    "is_sla_breached",
    "is_conformant",
    "variant_signature",
    "created_at",
    "updated_at",
)


def _workflow_automation_valid_graph():
    return {
        "swimlanes_json": json.dumps([{"id": "lane_1", "name": "Ops", "role": "Reviewer"}]),
        "nodes_json": json.dumps(
            [
                {"id": "n_start", "type": "start_event", "label": "Start", "lane_id": "lane_1"},
                {"id": "n_task", "type": "user_task", "label": "Review", "lane_id": "lane_1"},
                {"id": "n_end", "type": "end_event", "label": "Done", "lane_id": "lane_1"},
            ]
        ),
        "transitions_json": json.dumps(
            [
                {"from_node": "n_start", "to_node": "n_task", "label": "Begin"},
                {"from_node": "n_task", "to_node": "n_end", "label": "Finish"},
            ]
        ),
    }


def _workflow_automation_process_payload(**overrides):
    graph = _workflow_automation_valid_graph()
    data = {
        "name": "Contract Legal Triage",
        "code": "dbpm-form-01",
        "description": "Valid test blueprint.",
        "process_category": "contract_review",
        "trigger_event": "document_created",
        "target_document_type": "all",
        "version_number": "1",
        "sla_target_hours": "48",
        "is_active": "on",
        "swimlanes_json": graph["swimlanes_json"],
        "nodes_json": graph["nodes_json"],
        "transitions_json": graph["transitions_json"],
    }
    data.update(overrides)
    return data


def _workflow_automation_routing_payload(**overrides):
    data = {
        "name": "Confidential Legal Rule",
        "description": "Route confidential documents.",
        "rule_type": "routing_distribution",
        "trigger_event": "on_upload",
        "priority": "10",
        "target_document_type": "",
        "target_classification": "",
        "condition_logic_mode": "all_and",
        "conditions_json": json.dumps(
            [{"source": "document", "field": "classification", "op": "eq", "value": "confidential"}]
        ),
        "else_action_json": "{}",
        "validation_rules_json": "[]",
        "auto_populate_json": json.dumps({"document_fields": {"tags": "legal"}}),
        "route_action": "move_to_folder",
        "is_active": "on",
    }
    data.update(overrides)
    return data


def _workflow_automation_webhook_payload(**overrides):
    data = {
        "name": "Partner ERP Event Hook",
        "description": "Outbound DMS notification.",
        "direction": "outbound_webhook",
        "trigger_event": "process.completed",
        "target_url": "https://hooks.partner-erp.example/dms/events",
        "http_method": "post",
        "payload_format": "cloudevents_json",
        "custom_headers": json.dumps({"X-Tenant-Source": "NavERP"}),
        "payload_template_json": json.dumps({"env": "prod"}),
        "filter_document_type": "",
        "retry_policy_max": "5",
        "is_active": "on",
    }
    data.update(overrides)
    return data


def _workflow_automation_deep_nested_json(depth=22):
    node = 1
    for _ in range(depth):
        node = [node]
    return json.dumps(node)


def _workflow_automation_foreign_fixtures(tenant_b, admin_b):
    folder_b = DocumentFolder.objects.create(
        tenant=tenant_b,
        name="Tenant B Folder",
        slug="tenant-b-folder",
        path="/tenant-b-folder",
        owner=admin_b,
    )
    doc_b = Document.objects.create(
        tenant=tenant_b,
        title="Tenant B Secret Contract",
        document_type="contract",
        classification="confidential",
        status="published",
        owner=admin_b,
    )
    ver_b = DocumentVersion.objects.create(
        tenant=tenant_b,
        document=doc_b,
        version_label="1.0.0",
        major_number=1,
        minor_number=0,
        patch_number=0,
        version_type="major",
        status="approved",
        is_official=True,
        author=admin_b,
    )
    org_b = OrgUnit.objects.create(
        tenant=tenant_b,
        name="Globex Legal",
        kind="department",
    )
    role_b = Role.objects.create(
        tenant=tenant_b,
        name="Globex Reviewer",
    )
    wf_def_b = WorkflowDefinition.objects.create(
        tenant=tenant_b,
        name="Globex Core Workflow",
        module_slug="documents",
    )
    brule_b = BusinessRule.objects.create(
        tenant=tenant_b,
        name="Globex Core Rule",
        module_slug="documents",
    )
    conn_b = ConnectorDefinition.objects.create(
        tenant=tenant_b,
        name="Globex ERP Connector",
        category="erp",
    )
    proc_b = DocumentProcessDefinition.objects.create(
        tenant=tenant_b,
        name="Globex Published Flow",
        code="GLX-BPM-01",
        status="published",
        is_active=True,
        owner=admin_b,
        nodes_json=[
            {"id": "s", "type": "start_event", "label": "Start"},
            {"id": "e", "type": "end_event", "label": "End"},
        ],
        transitions_json=[{"from_node": "s", "to_node": "e"}],
    )
    return {
        "folder_b": folder_b,
        "doc_b": doc_b,
        "ver_b": ver_b,
        "org_b": org_b,
        "role_b": role_b,
        "wf_def_b": wf_def_b,
        "brule_b": brule_b,
        "conn_b": conn_b,
        "proc_b": proc_b,
    }


# ---------------------------------------------------------------------------
# 1. System Field Exclusions & Mass-Assignment Protection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "form_cls",
    [
        DocumentProcessDefinitionForm,
        DocumentRoutingRuleForm,
        DocumentProcessInstanceForm,
        DocumentWebhookTriggerForm,
    ],
)
def test_workflow_automation_forms_exclude_all_system_and_derived_fields(form_cls, tenant_a):
    form = form_cls(tenant=tenant_a)
    for forbidden in FORBIDDEN_SYSTEM_FIELDS:
        assert forbidden not in form.fields, (
            f"Mass-assignment risk: system field '{forbidden}' exposed on {form_cls.__name__}"
        )


def test_workflow_automation_forged_system_fields_ignored_on_save(
    tenant_a, admin_user, draft_process_definition, webhook_trigger
):
    proc_data = _workflow_automation_process_payload(
        name="Tampered Draft Name",
        code=draft_process_definition.code,
        status="published",
        number="DBPM-HACK",
        owner=str(admin_user.pk),
        instance_count="999",
    )
    proc_form = DocumentProcessDefinitionForm(
        data=proc_data, instance=draft_process_definition, tenant=tenant_a
    )
    assert proc_form.is_valid(), proc_form.errors
    saved_proc = proc_form.save()
    saved_proc.refresh_from_db()
    assert saved_proc.status == "draft"
    assert saved_proc.number != "DBPM-HACK"
    assert saved_proc.instance_count == 0

    wh_data = _workflow_automation_webhook_payload(
        name="Tampered Hook",
        fire_count="999",
        last_status="delivered",
        signing_secret="attacker-plaintext-secret",
    )
    wh_form = DocumentWebhookTriggerForm(data=wh_data, instance=webhook_trigger, tenant=tenant_a)
    assert wh_form.is_valid(), wh_form.errors
    saved_wh = wh_form.save()
    saved_wh.refresh_from_db()
    assert saved_wh.fire_count == 0
    assert saved_wh.last_status == "never_fired"
    assert saved_wh.signing_secret != "attacker-plaintext-secret"


# ---------------------------------------------------------------------------
# 2. Tenant Scoping, Active User Filtering & tenant=None Isolation (I3)
# ---------------------------------------------------------------------------


def test_workflow_automation_forms_tenant_none_resets_all_fk_querysets(
    process_definition, routing_rule, document, document_version
):
    proc_form = DocumentProcessDefinitionForm(tenant=None)
    for fname in ("target_folder", "department", "core_workflow_ref"):
        assert proc_form.fields[fname].queryset.count() == 0

    rule_form = DocumentRoutingRuleForm(tenant=None)
    for fname in (
        "process_definition",
        "core_rule_ref",
        "source_folder",
        "destination_folder",
        "route_to_org_unit",
        "route_to_role",
        "route_to_user",
    ):
        assert rule_form.fields[fname].queryset.count() == 0

    sim_form = RoutingRuleSimulatorForm(tenant=None)
    assert sim_form.fields["document"].queryset.count() == 0
    assert sim_form.fields["rule"].queryset.count() == 0

    inst_form = DocumentProcessInstanceForm(tenant=None)
    for fname in ("process_definition", "document", "version", "department", "current_assignee"):
        assert inst_form.fields[fname].queryset.count() == 0

    wh_form = DocumentWebhookTriggerForm(tenant=None)
    assert wh_form.fields["process_definition"].queryset.count() == 0
    assert wh_form.fields["connector_ref"].queryset.count() == 0

    ping_form = WebhookTestPingForm(tenant=None)
    assert ping_form.fields["document"].queryset.count() == 0


def test_workflow_automation_user_dropdowns_scope_to_active_tenant_users(
    tenant_a, tenant_b, admin_user, member_user, admin_b
):
    User = get_user_model()
    inactive_a = User.objects.create_user(
        username="inactive_a_bpm",
        email="inactive_a_bpm@acme.test",
        password="Password123!",
        tenant=tenant_a,
        is_active=False,
    )

    rule_form = DocumentRoutingRuleForm(tenant=tenant_a)
    rule_users = set(rule_form.fields["route_to_user"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in rule_users
    assert member_user.pk in rule_users
    assert inactive_a.pk not in rule_users
    assert admin_b.pk not in rule_users

    inst_form = DocumentProcessInstanceForm(tenant=tenant_a)
    assignees = set(inst_form.fields["current_assignee"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in assignees
    assert member_user.pk in assignees
    assert inactive_a.pk not in assignees
    assert admin_b.pk not in assignees


def test_workflow_automation_cross_tenant_fk_rejection_across_all_forms(
    tenant_a, tenant_b, admin_b, process_definition, document
):
    foreign = _workflow_automation_foreign_fixtures(tenant_b, admin_b)

    # DocumentProcessDefinitionForm foreign FKs
    for field_name, bad_pk in (
        ("target_folder", foreign["folder_b"].pk),
        ("department", foreign["org_b"].pk),
        ("core_workflow_ref", foreign["wf_def_b"].pk),
    ):
        form = DocumentProcessDefinitionForm(
            data=_workflow_automation_process_payload(code=f"FOREIGN-{field_name}", **{field_name: bad_pk}),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert field_name in form.errors

    # DocumentRoutingRuleForm foreign FKs
    for field_name, bad_pk in (
        ("process_definition", foreign["proc_b"].pk),
        ("core_rule_ref", foreign["brule_b"].pk),
        ("source_folder", foreign["folder_b"].pk),
        ("destination_folder", foreign["folder_b"].pk),
        ("route_to_org_unit", foreign["org_b"].pk),
        ("route_to_role", foreign["role_b"].pk),
        ("route_to_user", admin_b.pk),
    ):
        form = DocumentRoutingRuleForm(
            data=_workflow_automation_routing_payload(**{field_name: bad_pk}),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert field_name in form.errors

    # DocumentProcessInstanceForm foreign FKs
    for field_name, bad_pk in (
        ("process_definition", foreign["proc_b"].pk),
        ("document", foreign["doc_b"].pk),
        ("version", foreign["ver_b"].pk),
        ("department", foreign["org_b"].pk),
        ("current_assignee", admin_b.pk),
    ):
        payload = {
            "process_definition": process_definition.pk,
            "document": document.pk,
            field_name: bad_pk,
        }
        form = DocumentProcessInstanceForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors

    # DocumentWebhookTriggerForm foreign FKs
    for field_name, bad_pk in (
        ("process_definition", foreign["proc_b"].pk),
        ("connector_ref", foreign["conn_b"].pk),
    ):
        form = DocumentWebhookTriggerForm(
            data=_workflow_automation_webhook_payload(**{field_name: bad_pk}),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert field_name in form.errors

    # Direct reject_foreign helper verification
    helper_form = DocumentProcessDefinitionForm(
        data=_workflow_automation_process_payload(code="HELPER-CHECK"),
        tenant=tenant_a,
    )
    assert helper_form.is_valid(), helper_form.errors
    reject_foreign(helper_form, {"target_folder": foreign["folder_b"]}, ["target_folder"])
    assert "target_folder" in helper_form.errors
    assert "another workspace" in helper_form.errors["target_folder"][0]


# ---------------------------------------------------------------------------
# 3. DocumentProcessDefinitionForm & ProcessDesignerForm
# ---------------------------------------------------------------------------


def test_workflow_automation_process_definition_form_valid_create_and_code_uppercase(
    tenant_a, admin_user, document_folder, org_unit_a
):
    form = DocumentProcessDefinitionForm(
        data=_workflow_automation_process_payload(
            code="  lowercase-bpm-99  ",
            target_folder=document_folder.pk,
            department=org_unit_a.pk,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    proc = form.save(commit=False)
    proc.tenant = tenant_a
    proc.owner = admin_user
    proc.save()
    assert proc.code == "LOWERCASE-BPM-99"
    assert proc.number.startswith("DBPM-")
    assert proc.swimlanes_json[0]["id"] == "lane_1"


def test_workflow_automation_process_definition_form_boolean_widget_uses_form_check(tenant_a):
    form = DocumentProcessDefinitionForm(tenant=tenant_a)
    assert form.fields["is_active"].widget.attrs.get("class") == "form-check"


def test_workflow_automation_process_definition_form_duplicate_code_version_uniqueness(
    tenant_a, tenant_b, admin_b, process_definition
):
    # Duplicate (tenant_a, lowercase match, same version_number=1) fails on code
    dup_form = DocumentProcessDefinitionForm(
        data=_workflow_automation_process_payload(
            code=process_definition.code.lower(),
            version_number="1",
        ),
        tenant=tenant_a,
    )
    assert not dup_form.is_valid()
    assert "code" in dup_form.errors

    # Editing same instance keeps same (code, version_number) valid
    edit_form = DocumentProcessDefinitionForm(
        data=_workflow_automation_process_payload(
            code=process_definition.code,
            version_number=str(process_definition.version_number),
        ),
        instance=process_definition,
        tenant=tenant_a,
    )
    assert edit_form.is_valid(), edit_form.errors

    # Incrementing version_number in same tenant succeeds
    v2_form = DocumentProcessDefinitionForm(
        data=_workflow_automation_process_payload(
            code=process_definition.code,
            version_number="2",
        ),
        tenant=tenant_a,
    )
    assert v2_form.is_valid(), v2_form.errors

    # Same code and version_number in tenant_b succeeds
    b_form = DocumentProcessDefinitionForm(
        data=_workflow_automation_process_payload(
            code=process_definition.code,
            version_number="1",
        ),
        tenant=tenant_b,
    )
    assert b_form.is_valid(), b_form.errors
    b_obj = b_form.save(commit=False)
    b_obj.tenant = tenant_b
    b_obj.owner = admin_b
    b_obj.save()
    assert b_obj.pk is not None


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("code", "   "),
        ("version_number", "0"),
        ("version_number", "-1"),
        ("version_number", "NaN"),
        ("sla_target_hours", "0"),
        ("sla_target_hours", "-5"),
        ("sla_target_hours", "Infinity"),
        ("swimlanes_json", "{not json"),
        ("swimlanes_json", "{}"),
        ("nodes_json", '{"bad": "dict"}'),
        pytest.param("transitions_json", "[1,", id="bad-transitions-syntax"),
        pytest.param("nodes_json", "[" + "1," * 35000 + "1]", id="oversized-nodes-bytes"),
        pytest.param("transitions_json", _workflow_automation_deep_nested_json(22), id="deep-transitions"),
    ],
)
def test_workflow_automation_process_definition_form_rejects_invalid_inputs_and_caps(
    field, bad_value, tenant_a
):
    form = DocumentProcessDefinitionForm(
        data=_workflow_automation_process_payload(**{field: bad_value}),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert field in form.errors


def test_workflow_automation_published_blueprint_edit_validates_graph(
    tenant_a, process_definition
):
    # Published definition cannot save a graph missing end_event
    broken_nodes = json.dumps([{"id": "n_start", "type": "start_event", "label": "Start"}])
    form = DocumentProcessDefinitionForm(
        data=_workflow_automation_process_payload(
            code=process_definition.code,
            nodes_json=broken_nodes,
            transitions_json="[]",
        ),
        instance=process_definition,
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert form.non_field_errors()


def test_workflow_automation_process_designer_form_validates_graph_and_caps():
    valid_form = ProcessDesignerForm(data=_workflow_automation_valid_graph())
    assert valid_form.is_valid(), valid_form.errors

    # Empty nodes rejected
    empty_nodes = ProcessDesignerForm(
        data={"swimlanes_json": "[]", "nodes_json": "[]", "transitions_json": "[]"}
    )
    assert not empty_nodes.is_valid()
    assert "nodes_json" in empty_nodes.errors

    # Missing end_event
    no_end = ProcessDesignerForm(
        data={
            "swimlanes_json": "[]",
            "nodes_json": json.dumps([{"id": "s", "type": "start_event", "label": "Start"}]),
            "transitions_json": "[]",
        }
    )
    assert not no_end.is_valid()
    assert no_end.non_field_errors()

    # Unknown node type
    bad_type = ProcessDesignerForm(
        data={
            "swimlanes_json": "[]",
            "nodes_json": json.dumps(
                [
                    {"id": "s", "type": "start_event", "label": "Start"},
                    {"id": "x", "type": "unknown_bpmn_block", "label": "X"},
                    {"id": "e", "type": "end_event", "label": "End"},
                ]
            ),
            "transitions_json": "[]",
        }
    )
    assert not bad_type.is_valid()
    assert bad_type.non_field_errors()

    # Edge referencing unknown target node
    bad_edge = ProcessDesignerForm(
        data={
            "swimlanes_json": "[]",
            "nodes_json": json.dumps(
                [
                    {"id": "s", "type": "start_event", "label": "Start"},
                    {"id": "e", "type": "end_event", "label": "End"},
                ]
            ),
            "transitions_json": json.dumps([{"from_node": "s", "to_node": "missing_node"}]),
        }
    )
    assert not bad_edge.is_valid()
    assert bad_edge.non_field_errors()

    # Oversized >65536 byte and deep JSON caps
    too_big = ProcessDesignerForm(
        data={
            "swimlanes_json": "[]",
            "nodes_json": "[" + "1," * 35000 + "1]",
            "transitions_json": "[]",
        }
    )
    assert not too_big.is_valid()
    assert "nodes_json" in too_big.errors

    too_deep = ProcessDesignerForm(
        data={
            "swimlanes_json": _workflow_automation_deep_nested_json(22),
            "nodes_json": json.dumps([{"id": "s", "type": "start_event"}]),
            "transitions_json": "[]",
        }
    )
    assert not too_deep.is_valid()
    assert "swimlanes_json" in too_deep.errors


# ---------------------------------------------------------------------------
# 4. DocumentRoutingRuleForm & RoutingRuleSimulatorForm
# ---------------------------------------------------------------------------


def test_workflow_automation_routing_rule_form_valid_and_checkbox_classes(
    tenant_a, admin_user, document_folder, process_definition
):
    form = DocumentRoutingRuleForm(
        data=_workflow_automation_routing_payload(
            process_definition=process_definition.pk,
            destination_folder=document_folder.pk,
            route_to_user=admin_user.pk,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.fields["else_branch_enabled"].widget.attrs.get("class") == "form-check"
    assert form.fields["is_active"].widget.attrs.get("class") == "form-check"

    rule = form.save(commit=False)
    rule.tenant = tenant_a
    rule.owner = admin_user
    rule.save()
    assert rule.number.startswith("DRUL-")


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("priority", "0"),
        ("priority", "-2"),
        ("priority", "NaN"),
        ("conditions_json", "{}"),
        ("conditions_json", json.dumps(["not-a-dict"])),
        ("conditions_json", json.dumps([{"source": "document", "field": "title", "op": "like_sql", "value": "x"}])),
        ("conditions_json", json.dumps([{"source": "document", "field": "title", "op": "regex_match", "value": "[unclosed"}])),
        ("conditions_json", json.dumps([{"source": "document", "field": "title", "op": "regex_match", "value": "(a+)+"}])),
        ("conditions_json", json.dumps([{"source": "document", "field": "title", "op": "regex_match", "value": "(.*)*"}])),
        pytest.param(
            "conditions_json",
            json.dumps([{"source": "document", "field": "title", "op": "regex_match", "value": "a" * 205}]),
            id="regex-too-long",
        ),
        pytest.param("conditions_json", "[" + "1," * 35000 + "1]", id="oversized-conditions-bytes"),
        ("validation_rules_json", "{}"),
        ("validation_rules_json", json.dumps([{"check": "unsupported_gate"}])),
        ("validation_rules_json", json.dumps([{"check": "required_metadata", "field": "   "}])),
        ("validation_rules_json", json.dumps([{"check": "not_status", "field": ""}])),
        ("validation_rules_json", json.dumps([{"check": "min_ocr_confidence", "min_confidence": "abc"}])),
        ("validation_rules_json", json.dumps([{"check": "min_ocr_confidence", "min_confidence": "NaN"}])),
        ("validation_rules_json", json.dumps([{"check": "min_ocr_confidence", "min_confidence": "Infinity"}])),
        ("auto_populate_json", "[]"),
        ("auto_populate_json", "{bad json"),
        ("else_action_json", "[]"),
        ("else_action_json", _workflow_automation_deep_nested_json(22)),
    ],
)
def test_workflow_automation_routing_rule_form_rejects_invalid_configs_and_redos(
    field, bad_value, tenant_a
):
    form = DocumentRoutingRuleForm(
        data=_workflow_automation_routing_payload(**{field: bad_value}),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert field in form.errors


def test_workflow_automation_routing_rule_form_block_validation_and_else_action(tenant_a):
    # block_validation requires non-empty validation_rules_json
    block_empty = DocumentRoutingRuleForm(
        data=_workflow_automation_routing_payload(
            route_action="block_validation",
            validation_rules_json="[]",
        ),
        tenant=tenant_a,
    )
    assert not block_empty.is_valid()
    assert "validation_rules_json" in block_empty.errors

    # block_validation with valid validation_rules_json passes
    block_ok = DocumentRoutingRuleForm(
        data=_workflow_automation_routing_payload(
            route_action="block_validation",
            validation_rules_json=json.dumps(
                [
                    {"check": "required_metadata", "field": "contract_id"},
                    {"check": "min_ocr_confidence", "min_confidence": "0.85"},
                ]
            ),
        ),
        tenant=tenant_a,
    )
    assert block_ok.is_valid(), block_ok.errors

    # else_branch_enabled rejects unsupported else route_action
    bad_else = DocumentRoutingRuleForm(
        data=_workflow_automation_routing_payload(
            else_branch_enabled="on",
            else_action_json=json.dumps({"route_action": "delete_everything"}),
        ),
        tenant=tenant_a,
    )
    assert not bad_else.is_valid()
    assert "else_action_json" in bad_else.errors

    # else_branch_enabled accepts supported else route_action
    ok_else = DocumentRoutingRuleForm(
        data=_workflow_automation_routing_payload(
            else_branch_enabled="on",
            else_action_json=json.dumps({"route_action": "assign_role"}),
        ),
        tenant=tenant_a,
    )
    assert ok_else.is_valid(), ok_else.errors


def test_workflow_automation_routing_rule_simulator_form_scoping_and_validation(
    tenant_a, tenant_b, admin_b, document, routing_rule
):
    foreign = _workflow_automation_foreign_fixtures(tenant_b, admin_b)

    form = RoutingRuleSimulatorForm(tenant=tenant_a)
    assert form.fields["apply_mutations"].widget.attrs.get("class") == "form-check"
    assert document in form.fields["document"].queryset
    assert foreign["doc_b"] not in form.fields["document"].queryset
    assert routing_rule in form.fields["rule"].queryset

    # Valid with blank optional rule
    valid_sim = RoutingRuleSimulatorForm(
        data={"document": document.pk, "rule": "", "trigger_event": "", "apply_mutations": ""},
        tenant=tenant_a,
    )
    assert valid_sim.is_valid(), valid_sim.errors

    # Foreign document rejected
    foreign_sim = RoutingRuleSimulatorForm(
        data={"document": foreign["doc_b"].pk},
        tenant=tenant_a,
    )
    assert not foreign_sim.is_valid()
    assert "document" in foreign_sim.errors


# ---------------------------------------------------------------------------
# 5. DocumentProcessInstanceForm & ProcessAdvanceForm
# ---------------------------------------------------------------------------


def test_workflow_automation_process_instance_form_create_excludes_non_published_blueprints(
    tenant_a, admin_user, process_definition, draft_process_definition, document
):
    deprecated_proc = DocumentProcessDefinition.objects.create(
        tenant=tenant_a,
        name="Deprecated Blueprint",
        code="DBPM-DEPR",
        status="deprecated",
        is_active=True,
        owner=admin_user,
    )
    inactive_pub = DocumentProcessDefinition.objects.create(
        tenant=tenant_a,
        name="Inactive Published Blueprint",
        code="DBPM-INACT",
        status="published",
        is_active=False,
        owner=admin_user,
    )

    create_form = DocumentProcessInstanceForm(tenant=tenant_a)
    allowed_pks = set(
        create_form.fields["process_definition"].queryset.values_list("pk", flat=True)
    )
    assert process_definition.pk in allowed_pks
    assert draft_process_definition.pk not in allowed_pks
    assert deprecated_proc.pk not in allowed_pks
    assert inactive_pub.pk not in allowed_pks

    for bad_proc in (draft_process_definition, deprecated_proc, inactive_pub):
        bound = DocumentProcessInstanceForm(
            data={"process_definition": bad_proc.pk, "document": document.pk},
            tenant=tenant_a,
        )
        assert not bound.is_valid()
        assert "process_definition" in bound.errors


def test_workflow_automation_process_instance_form_version_scoping_and_cross_doc_rejection(
    tenant_a, admin_user, process_definition, document, document_version, target_document, org_unit_a
):
    other_ver = DocumentVersion.objects.create(
        tenant=tenant_a,
        document=target_document,
        version_label="2.0.0",
        major_number=2,
        minor_number=0,
        patch_number=0,
        version_type="major",
        status="approved",
        is_official=True,
        author=admin_user,
    )

    # Bound form scopes version queryset to chosen document_id
    scoped_form = DocumentProcessInstanceForm(
        data={
            "process_definition": process_definition.pk,
            "document": document.pk,
            "version": document_version.pk,
            "department": org_unit_a.pk,
            "current_assignee": admin_user.pk,
            "context_variables_json": json.dumps({"tier": "gold"}),
        },
        tenant=tenant_a,
    )
    assert document_version in scoped_form.fields["version"].queryset
    assert other_ver not in scoped_form.fields["version"].queryset
    assert scoped_form.is_valid(), scoped_form.errors

    # Initial scoping also narrows version queryset cleanly while direct cross-doc mismatch fails clean()
    mismatch_form = DocumentProcessInstanceForm(
        data={
            "process_definition": process_definition.pk,
            "document": document.pk,
            "version": other_ver.pk,
        },
        tenant=tenant_a,
    )
    assert not mismatch_form.is_valid()
    assert "version" in mismatch_form.errors

    # Oversized / list JSON rejected in context_variables_json
    bad_ctx = DocumentProcessInstanceForm(
        data={
            "process_definition": process_definition.pk,
            "document": document.pk,
            "context_variables_json": "[]",
        },
        tenant=tenant_a,
    )
    assert not bad_ctx.is_valid()
    assert "context_variables_json" in bad_ctx.errors


def test_workflow_automation_process_instance_edit_disables_immutable_fks(
    tenant_a, process_instance, draft_process_definition, target_document, member_user
):
    edit_form = DocumentProcessInstanceForm(instance=process_instance, tenant=tenant_a)
    assert edit_form.fields["process_definition"].disabled is True
    assert edit_form.fields["document"].disabled is True

    # Attempt to POST swapped document/process_definition keeps existing values
    tampered_form = DocumentProcessInstanceForm(
        data={
            "process_definition": draft_process_definition.pk,
            "document": target_document.pk,
            "current_assignee": member_user.pk,
            "context_variables_json": json.dumps({"note": "updated"}),
        },
        instance=process_instance,
        tenant=tenant_a,
    )
    assert tampered_form.is_valid(), tampered_form.errors
    saved = tampered_form.save()
    saved.refresh_from_db()
    assert saved.process_definition_id == process_instance.process_definition_id
    assert saved.document_id == process_instance.document_id
    assert saved.current_assignee_id == member_user.pk


def test_workflow_automation_process_advance_form_choices_and_notes_bounds():
    expected = ["approved", "rejected", "escalated", "completed"]
    assert [c[0] for c in ProcessAdvanceForm.OUTCOME_CHOICES] == expected

    for outcome in expected:
        f = ProcessAdvanceForm(data={"outcome": outcome, "notes": "x" * 200})
        assert f.is_valid(), f.errors

    empty_outcome = ProcessAdvanceForm(data={"outcome": "", "notes": "ok"})
    assert not empty_outcome.is_valid()
    assert "outcome" in empty_outcome.errors

    bad_outcome = ProcessAdvanceForm(data={"outcome": "force_delete"})
    assert not bad_outcome.is_valid()
    assert "outcome" in bad_outcome.errors

    long_notes = ProcessAdvanceForm(data={"outcome": "approved", "notes": "x" * 201})
    assert not long_notes.is_valid()
    assert "notes" in long_notes.errors


# ---------------------------------------------------------------------------
# 6. DocumentWebhookTriggerForm & WebhookTestPingForm
# ---------------------------------------------------------------------------


def test_workflow_automation_webhook_trigger_form_valid_outbound_and_inbound(
    tenant_a, admin_user, process_definition
):
    outbound_form = DocumentWebhookTriggerForm(
        data=_workflow_automation_webhook_payload(
            process_definition=process_definition.pk,
            custom_headers=json.dumps({"  X-Custom-Auth  ": "token-abc"}),
        ),
        tenant=tenant_a,
    )
    assert outbound_form.fields["is_active"].widget.attrs.get("class") == "form-check"
    assert outbound_form.is_valid(), outbound_form.errors
    assert outbound_form.cleaned_data["custom_headers"] == {"X-Custom-Auth": "token-abc"}

    # Outbound / middleware_callback require target_url
    for direction in ("outbound_webhook", "middleware_callback"):
        missing_url = DocumentWebhookTriggerForm(
            data=_workflow_automation_webhook_payload(direction=direction, target_url=""),
            tenant=tenant_a,
        )
        assert not missing_url.is_valid()
        assert "target_url" in missing_url.errors

    # Inbound webhook permits empty target_url
    inbound_ok = DocumentWebhookTriggerForm(
        data=_workflow_automation_webhook_payload(
            direction="inbound_webhook",
            trigger_event="inbound.trigger",
            target_url="",
        ),
        tenant=tenant_a,
    )
    assert inbound_ok.is_valid(), inbound_ok.errors


@pytest.mark.parametrize(
    "ssrf_url",
    [
        "http://127.0.0.1/hook",
        "http://localhost/hook",
        "http://[::1]/hook",
        "http://[::ffff:127.0.0.1]/hook",
        "http://[64:ff9b::169.254.169.254]/latest",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata/computeMetadata/v1/",
        "http://instance-data/latest/",
        "https://10.0.0.1/internal",
        "https://100.64.0.1/cgnat",
        "https://user:pass@hooks.partner-erp.example/cb",
        "ftp://hooks.partner-erp.example/cb",
        "http://2130706433/int-loopback",
        "https://hooks.partner-erp.example/a\\b",
        "http://[::ffff:127.0.0.1%25eth0]/",
    ],
)
def test_workflow_automation_webhook_form_rejects_ssrf_urls(ssrf_url, tenant_a):
    form = DocumentWebhookTriggerForm(
        data=_workflow_automation_webhook_payload(target_url=ssrf_url),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "target_url" in form.errors


@pytest.mark.parametrize(
    "bad_headers",
    [
        "[]",
        "{bad json",
        json.dumps({"X-Num": 123}),
        json.dumps({"Bad Header Name": "ok"}),
        json.dumps({"   ": "blank-key"}),
        json.dumps({"X-Test": "line1\r\nInjected: 1"}),
        json.dumps({"X-Test": "line1\nline2"}),
        json.dumps({"X-Test": "null\x00byte"}),
        json.dumps({"Authorization": "Bearer leak"}),
        json.dumps({"authorization": "Bearer lowercase"}),
        json.dumps({"Host": "evil.internal"}),
        json.dumps({"Cookie": "sessionid=abc"}),
        json.dumps({"Content-Length": "10"}),
        json.dumps({"Transfer-Encoding": "chunked"}),
        json.dumps({"Connection": "keep-alive"}),
        json.dumps({"X-NavERP-Signature-256": "forged"}),
        json.dumps({"x-naverp-signature-256": "forged-lower"}),
        json.dumps({"X-Dup": "1", "x-dup": "2"}),
        pytest.param(json.dumps({f"X-H{i}": "v" for i in range(26)}), id="too-many-headers"),
        pytest.param(json.dumps({"X-Long": "a" * 2049}), id="oversized-header-val"),
    ],
)
def test_workflow_automation_webhook_form_rejects_invalid_or_forbidden_headers(
    bad_headers, tenant_a
):
    form = DocumentWebhookTriggerForm(
        data=_workflow_automation_webhook_payload(custom_headers=bad_headers),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "custom_headers" in form.errors


def test_workflow_automation_webhook_form_retry_policy_and_template_caps(tenant_a):
    base_form = DocumentWebhookTriggerForm(tenant=tenant_a)
    assert int(base_form.fields["retry_policy_max"].widget.attrs.get("min")) == 0
    assert int(base_form.fields["retry_policy_max"].widget.attrs.get("max")) == 20

    for valid_retry in ("0", "5", "20"):
        ok_form = DocumentWebhookTriggerForm(
            data=_workflow_automation_webhook_payload(retry_policy_max=valid_retry),
            tenant=tenant_a,
        )
        assert ok_form.is_valid(), ok_form.errors

    for bad_retry in ("-1", "NaN", "", "abc"):
        bad_form = DocumentWebhookTriggerForm(
            data=_workflow_automation_webhook_payload(retry_policy_max=bad_retry),
            tenant=tenant_a,
        )
        assert not bad_form.is_valid()
        assert "retry_policy_max" in bad_form.errors

    bad_tpl = DocumentWebhookTriggerForm(
        data=_workflow_automation_webhook_payload(
            payload_template_json=_workflow_automation_deep_nested_json(22)
        ),
        tenant=tenant_a,
    )
    assert not bad_tpl.is_valid()
    assert "payload_template_json" in bad_tpl.errors


def test_workflow_automation_webhook_test_ping_form_scoping_and_validation(
    tenant_a, tenant_b, admin_b, document
):
    foreign = _workflow_automation_foreign_fixtures(tenant_b, admin_b)

    form = WebhookTestPingForm(tenant=tenant_a)
    assert document in form.fields["document"].queryset
    assert foreign["doc_b"] not in form.fields["document"].queryset

    # Empty optional document allowed
    ok_empty = WebhookTestPingForm(data={"event_override": "custom.ping", "document": ""}, tenant=tenant_a)
    assert ok_empty.is_valid(), ok_empty.errors

    # Tenant document allowed
    ok_doc = WebhookTestPingForm(data={"event_override": "", "document": document.pk}, tenant=tenant_a)
    assert ok_doc.is_valid(), ok_doc.errors

    # Foreign document rejected
    bad_doc = WebhookTestPingForm(data={"document": foreign["doc_b"].pk}, tenant=tenant_a)
    assert not bad_doc.is_valid()
    assert "document" in bad_doc.errors

    # Over-length event_override rejected (>60)
    bad_ev = WebhookTestPingForm(data={"event_override": "e" * 61}, tenant=tenant_a)
    assert not bad_ev.is_valid()
    assert "event_override" in bad_ev.errors
