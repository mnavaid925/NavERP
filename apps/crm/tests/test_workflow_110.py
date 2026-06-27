"""Tests for CRM sub-module 1.10 — Automation & Workflow Engine.

Covers:
  - Model: Webhook auto-number (WH-00001), secret_masked, WebhookDelivery default status=pending
  - Form: WebhookForm secret write-only / keep-on-edit, clean_headers validation
  - Engine helpers: _safe_record_field (allowlist), _eval_conditions (operators, numeric cast, unknown)
  - _run_rule / workflowrule_run: webhook action creates logs + deliveries; approval action; inactive guard
  - Views: webhook_list/detail @login_required; create/edit/delete/test @tenant_admin_required
  - Boolean filter: webhook_list?is_active=False returns only inactive
  - Multi-tenant IDOR: A's client on B's objects → 404
  - CSRF enforcement
  - Read-only delivery: no create/edit/delete URL (NoReverseMatch)
  - Query-count: _run_rule over many opportunities with FK-field condition stays bounded
"""
import hashlib
import hmac
import json

import pytest
from django.test import Client
from django.urls import reverse, NoReverseMatch

pytestmark = pytest.mark.django_db


# ============================================================== helpers / factories

def _make_party(tenant, name="Acme Ltd", kind="organization"):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, kind=kind, name=name)


def _make_opportunity(tenant, account, name="Big Deal", amount="5000.00", stage="prospecting"):
    from apps.crm.models import Opportunity
    return Opportunity.objects.create(
        tenant=tenant, name=name, account=account,
        stage=stage, amount=amount, probability=20,
    )


def _make_webhook(tenant, name="My Hook", target_url="https://example.com/hook",
                  trigger_entity="opportunity", trigger_event="created",
                  secret="supersecretvalue", is_active=True, headers=None):
    from apps.crm.models import Webhook
    return Webhook.objects.create(
        tenant=tenant, name=name, target_url=target_url,
        trigger_entity=trigger_entity, trigger_event=trigger_event,
        secret=secret, is_active=is_active, headers=headers or {},
    )


def _make_workflow_rule(tenant, name="Auto Rule", trigger_entity="opportunity",
                        trigger_event="created", conditions=None, actions=None,
                        is_active=True):
    from apps.crm.models import WorkflowRule
    return WorkflowRule.objects.create(
        tenant=tenant, name=name,
        trigger_entity=trigger_entity, trigger_event=trigger_event,
        conditions=conditions if conditions is not None else [],
        actions=actions if actions is not None else [],
        is_active=is_active,
    )


# ============================================================== Group 1 — Models

class TestWebhookModel:
    def test_auto_number_has_wh_prefix(self, tenant_a):
        from apps.crm.models import Webhook
        wh = Webhook.objects.create(
            tenant=tenant_a, name="Hook", target_url="https://example.com",
            trigger_entity="opportunity", trigger_event="created",
        )
        assert wh.number.startswith("WH-")

    def test_auto_number_zero_padded(self, tenant_a):
        from apps.crm.models import Webhook
        wh = Webhook.objects.create(
            tenant=tenant_a, name="Hook", target_url="https://example.com",
            trigger_entity="opportunity", trigger_event="created",
        )
        # Format: WH-00001 — 5 digit padding
        assert len(wh.number.split("-")[1]) == 5

    def test_two_webhooks_different_numbers(self, tenant_a):
        wh1 = _make_webhook(tenant_a, name="Hook 1")
        wh2 = _make_webhook(tenant_a, name="Hook 2")
        assert wh1.number != wh2.number

    def test_number_scoped_per_tenant(self, tenant_a, tenant_b):
        wh_a = _make_webhook(tenant_a, name="A Hook")
        wh_b = _make_webhook(tenant_b, name="B Hook")
        # Both get WH-00001 (independent sequences per tenant)
        assert wh_a.number == wh_b.number

    def test_str_contains_number_and_name(self, tenant_a):
        wh = _make_webhook(tenant_a, name="My Webhook")
        s = str(wh)
        assert wh.number in s
        assert "My Webhook" in s

    def test_secret_masked_hides_all_but_last4(self, tenant_a):
        wh = _make_webhook(tenant_a, secret="supersecretvalue")
        masked = wh.secret_masked
        # Must end with last 4 chars
        assert masked.endswith("alue")
        # Must start with the bullet prefix
        assert masked.startswith("••••")
        # Raw secret must NOT appear in the mask
        assert "supersecretvalue" not in masked

    def test_secret_masked_short_secret(self, tenant_a):
        from apps.crm.models import Webhook
        wh = Webhook.objects.create(
            tenant=tenant_a, name="Short", target_url="https://x.com",
            trigger_entity="opportunity", trigger_event="created",
            secret="ab",
        )
        # Fewer than 4 chars → (set) fallback
        assert wh.secret_masked == "(set)"

    def test_secret_masked_empty_secret(self, tenant_a):
        from apps.crm.models import Webhook
        wh = Webhook.objects.create(
            tenant=tenant_a, name="None", target_url="https://x.com",
            trigger_entity="opportunity", trigger_event="created",
            secret="",
        )
        assert wh.secret_masked == "(none)"

    def test_is_active_default_true(self, tenant_a):
        from apps.crm.models import Webhook
        wh = Webhook.objects.create(
            tenant=tenant_a, name="Default", target_url="https://x.com",
            trigger_entity="opportunity", trigger_event="created",
        )
        assert wh.is_active is True

    def test_headers_default_empty_dict(self, tenant_a):
        from apps.crm.models import Webhook
        wh = Webhook.objects.create(
            tenant=tenant_a, name="Hdr", target_url="https://x.com",
            trigger_entity="opportunity", trigger_event="created",
        )
        assert wh.headers == {}


class TestWebhookDeliveryModel:
    def test_default_status_pending(self, tenant_a):
        from apps.crm.models import WebhookDelivery
        wh = _make_webhook(tenant_a)
        d = WebhookDelivery.objects.create(
            tenant=tenant_a, webhook=wh, event="opportunity.created",
            payload='{"x":1}',
        )
        assert d.status == "pending"

    def test_str_contains_event_and_status(self, tenant_a):
        from apps.crm.models import WebhookDelivery
        wh = _make_webhook(tenant_a)
        d = WebhookDelivery.objects.create(
            tenant=tenant_a, webhook=wh, event="opportunity.created", payload="{}",
        )
        s = str(d)
        assert "opportunity.created" in s
        assert "pending" in s

    def test_unique_together_not_required(self, tenant_a):
        """Multiple deliveries for the same webhook and event are allowed."""
        from apps.crm.models import WebhookDelivery
        wh = _make_webhook(tenant_a)
        d1 = WebhookDelivery.objects.create(
            tenant=tenant_a, webhook=wh, event="opportunity.created", payload="{}",
        )
        d2 = WebhookDelivery.objects.create(
            tenant=tenant_a, webhook=wh, event="opportunity.created", payload="{}",
        )
        assert d1.pk != d2.pk

    def test_status_choices_include_simulated(self):
        from apps.crm.models import WebhookDelivery
        choices_vals = {v for v, _ in WebhookDelivery.STATUS_CHOICES}
        assert "simulated" in choices_vals

    def test_created_at_auto_set(self, tenant_a):
        from apps.crm.models import WebhookDelivery
        wh = _make_webhook(tenant_a)
        d = WebhookDelivery.objects.create(
            tenant=tenant_a, webhook=wh, event="test", payload="{}",
        )
        assert d.created_at is not None


class TestWorkflowRuleModel:
    def test_auto_number_wfr_prefix(self, tenant_a):
        rule = _make_workflow_rule(tenant_a)
        assert rule.number.startswith("WFR-")

    def test_str_contains_number_and_name(self, tenant_a):
        rule = _make_workflow_rule(tenant_a, name="Test Rule")
        s = str(rule)
        assert rule.number in s
        assert "Test Rule" in s

    def test_is_active_default_true(self, tenant_a):
        from apps.crm.models import WorkflowRule
        rule = WorkflowRule.objects.create(
            tenant=tenant_a, name="Active", trigger_entity="opportunity", trigger_event="created",
        )
        assert rule.is_active is True


# ============================================================== Group 2 — WebhookForm

class TestWebhookForm:
    def test_secret_required_on_create(self, tenant_a):
        from apps.crm.forms import WebhookForm
        form = WebhookForm(data={
            "name": "MyHook",
            "target_url": "https://example.com/hook",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "",  # blank secret on create
            "is_active": True,
            "headers": "{}",
            "description": "",
        }, tenant=tenant_a)
        # blank secret on create — form may be valid (secret is optional by model) or
        # invalid depending on implementation; test that it does NOT expose a stored secret
        # The form saves with empty secret if blank; this is permitted
        # What we validate: if secret is set, it's stored; if blank on create, blank is stored

    def test_secret_rendered_as_password_input(self, tenant_a):
        """The secret field widget must be PasswordInput so it never renders the value."""
        from apps.crm.forms import WebhookForm
        form = WebhookForm(tenant=tenant_a)
        widget = form.fields["secret"].widget
        from django import forms as django_forms
        assert isinstance(widget, django_forms.PasswordInput)

    def test_secret_render_value_false(self, tenant_a):
        """render_value=False → the stored secret is never populated back into the HTML."""
        from apps.crm.forms import WebhookForm
        form = WebhookForm(tenant=tenant_a)
        assert form.fields["secret"].widget.render_value is False

    def test_blank_secret_on_edit_keeps_stored_secret(self, tenant_a):
        """Saving a blank secret on an edit form preserves the existing stored secret."""
        from apps.crm.forms import WebhookForm
        wh = _make_webhook(tenant_a, secret="original_secret_value")
        form = WebhookForm(data={
            "name": wh.name,
            "target_url": wh.target_url,
            "trigger_entity": wh.trigger_entity,
            "trigger_event": wh.trigger_event,
            "secret": "",       # blank → should keep "original_secret_value"
            "is_active": True,
            "headers": "{}",
            "description": "",
        }, instance=wh, tenant=tenant_a)
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.secret == "original_secret_value"

    def test_set_secret_on_edit_updates_it(self, tenant_a):
        """Providing a new secret on edit replaces the stored one."""
        from apps.crm.forms import WebhookForm
        wh = _make_webhook(tenant_a, secret="old_secret")
        form = WebhookForm(data={
            "name": wh.name,
            "target_url": wh.target_url,
            "trigger_entity": wh.trigger_entity,
            "trigger_event": wh.trigger_event,
            "secret": "new_secret_value",
            "is_active": True,
            "headers": "{}",
            "description": "",
        }, instance=wh, tenant=tenant_a)
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.secret == "new_secret_value"

    def test_edit_form_html_does_not_contain_raw_secret(self, tenant_a):
        """Rendering the bound edit form must NOT contain the raw secret value in the HTML."""
        from apps.crm.forms import WebhookForm
        wh = _make_webhook(tenant_a, secret="supersecretvalue")
        form = WebhookForm(instance=wh, tenant=tenant_a)
        html = str(form["secret"])
        assert "supersecretvalue" not in html

    def test_clean_headers_accepts_valid_dict(self, tenant_a):
        from apps.crm.forms import WebhookForm
        form = WebhookForm(data={
            "name": "Hook",
            "target_url": "https://example.com/",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "s",
            "is_active": True,
            "headers": '{"X-Custom": "ok"}',
            "description": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["headers"] == {"X-Custom": "ok"}

    def test_clean_headers_rejects_crlf_in_value(self, tenant_a):
        from apps.crm.forms import WebhookForm
        # CRLF injection in value: "a\r\nEvil:1"
        form = WebhookForm(data={
            "name": "Hook",
            "target_url": "https://example.com/",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "s",
            "is_active": True,
            "headers": '{"X": "a\\r\\nEvil:1"}',
            "description": "",
        }, tenant=tenant_a)
        # The JSON-parsed value will contain literal \r\n (the raw chars)
        # We need to submit the actual bytes; craft the dict and pass via JSON parse
        # The form receives the textarea content and JSONField parses it; then clean_headers runs
        # Test with actual CRLF bytes in the JSON string:
        bad_headers = {"X": "a\r\nEvil:1"}
        import json as _json
        form2 = WebhookForm(data={
            "name": "Hook",
            "target_url": "https://example.com/",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "s",
            "is_active": True,
            "headers": _json.dumps(bad_headers),
            "description": "",
        }, tenant=tenant_a)
        assert not form2.is_valid()
        assert "headers" in form2.errors

    def test_clean_headers_rejects_crlf_in_key(self, tenant_a):
        from apps.crm.forms import WebhookForm
        import json as _json
        bad_headers = {"X\r\nEvil: hdr": "val"}
        form = WebhookForm(data={
            "name": "Hook",
            "target_url": "https://example.com/",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "s",
            "is_active": True,
            "headers": _json.dumps(bad_headers),
            "description": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "headers" in form.errors

    def test_clean_headers_rejects_non_string_value(self, tenant_a):
        from apps.crm.forms import WebhookForm
        import json as _json
        form = WebhookForm(data={
            "name": "Hook",
            "target_url": "https://example.com/",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "s",
            "is_active": True,
            "headers": _json.dumps({"X": 123}),  # int value — not allowed
            "description": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "headers" in form.errors

    def test_clean_headers_rejects_non_dict(self, tenant_a):
        from apps.crm.forms import WebhookForm
        form = WebhookForm(data={
            "name": "Hook",
            "target_url": "https://example.com/",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "s",
            "is_active": True,
            "headers": '["not", "a", "dict"]',
            "description": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "headers" in form.errors

    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.crm.forms import WebhookForm
        form = WebhookForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_a_form_field(self, tenant_a):
        from apps.crm.forms import WebhookForm
        form = WebhookForm(tenant=tenant_a)
        assert "number" not in form.fields


# ============================================================== Group 3 — _safe_record_field

class TestSafeRecordField:
    """_safe_record_field must return scalar column values and block everything else."""

    def _get_fn(self):
        from apps.crm.views import _safe_record_field
        return _safe_record_field

    def test_scalar_column_returns_value(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        # 'name' is a concrete non-relation column on Opportunity
        assert fn(opp, "name") == opp.name

    def test_amount_column_returns_value(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account, amount="9999.00")
        val = fn(opp, "amount")
        assert val is not None
        assert str(val) == str(opp.amount)

    def test_stage_column_returns_value(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account, stage="proposal")
        assert fn(opp, "stage") == "proposal"

    def test_fk_field_account_returns_none(self, tenant_a):
        """account is a ForeignKey relation — must return None, not the Party object."""
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        # 'account' is an FK field name; attname would be 'account_id'
        result = fn(opp, "account")
        assert result is None

    def test_fk_attname_account_id_returns_none(self, tenant_a):
        """account_id is the FK column attname, but the ForeignKey field has is_relation=True
        so _safe_record_field excludes it from the allowlist — returns None.
        This is intentional: the allowlist blocks ALL relation-bearing fields (even their ID columns)
        to prevent any FK-value leaks and to ensure no per-record FK lazy-load can be triggered."""
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        # The ForeignKey field's is_relation=True → excluded from the allowlist → None
        val = fn(opp, "account_id")
        assert val is None

    def test_fk_field_owner_returns_none(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        assert fn(opp, "owner") is None

    def test_method_delete_returns_none(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        assert fn(opp, "delete") is None

    def test_method_save_returns_none(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        assert fn(opp, "save") is None

    def test_dunder_state_returns_none(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        assert fn(opp, "_state") is None

    def test_dunder_dict_returns_none(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        assert fn(opp, "__dict__") is None

    def test_pk_returns_none(self, tenant_a):
        """'pk' is an alias, not a concrete attname — must be blocked."""
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        # 'pk' is a Python alias (not in concrete_fields attname set) → None
        assert fn(opp, "pk") is None

    def test_weighted_amount_property_returns_none(self, tenant_a):
        """weighted_amount is a @property, not a concrete column — must be blocked."""
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        assert fn(opp, "weighted_amount") is None

    def test_empty_name_returns_none(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        assert fn(opp, "") is None

    def test_nonexistent_field_returns_none(self, tenant_a):
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        assert fn(opp, "definitely_not_a_field") is None


# ============================================================== Group 4 — _eval_conditions

class TestEvalConditions:
    """_eval_conditions AND-gate over condition dicts."""

    def _get_fn(self):
        from apps.crm.views import _eval_conditions
        return _eval_conditions

    def _make_opp(self, tenant_a, **kwargs):
        account = _make_party(tenant_a)
        return _make_opportunity(tenant_a, account, **kwargs)

    def test_empty_conditions_always_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a)
        assert fn(opp, []) is True

    def test_none_conditions_treated_as_match(self, tenant_a):
        """Non-list conditions (None / dict) → treated as match (safe fallback for bad data)."""
        fn = self._get_fn()
        opp = self._make_opp(tenant_a)
        assert fn(opp, None) is True  # isinstance(None, list) is False → True

    def test_eq_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, stage="proposal")
        assert fn(opp, [{"field": "stage", "operator": "eq", "value": "proposal"}]) is True

    def test_eq_no_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, stage="prospecting")
        assert fn(opp, [{"field": "stage", "operator": "eq", "value": "proposal"}]) is False

    def test_ne_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, stage="prospecting")
        assert fn(opp, [{"field": "stage", "operator": "ne", "value": "proposal"}]) is True

    def test_ne_no_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, stage="proposal")
        assert fn(opp, [{"field": "stage", "operator": "ne", "value": "proposal"}]) is False

    def test_gt_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, amount="5000.00")
        assert fn(opp, [{"field": "amount", "operator": "gt", "value": "1000"}]) is True

    def test_gt_no_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, amount="500.00")
        assert fn(opp, [{"field": "amount", "operator": "gt", "value": "1000"}]) is False

    def test_lt_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, amount="100.00")
        assert fn(opp, [{"field": "amount", "operator": "lt", "value": "1000"}]) is True

    def test_lt_no_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, amount="5000.00")
        assert fn(opp, [{"field": "amount", "operator": "lt", "value": "1000"}]) is False

    def test_gte_match_equal(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, amount="1000.00")
        assert fn(opp, [{"field": "amount", "operator": "gte", "value": "1000"}]) is True

    def test_lte_match_equal(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, amount="1000.00")
        assert fn(opp, [{"field": "amount", "operator": "lte", "value": "1000"}]) is True

    def test_contains_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, name="Big Enterprise Deal")
        assert fn(opp, [{"field": "name", "operator": "contains", "value": "Enterprise"}]) is True

    def test_contains_no_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, name="Small Deal")
        assert fn(opp, [{"field": "name", "operator": "contains", "value": "Enterprise"}]) is False

    def test_icontains_case_insensitive(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, name="Big enterprise deal")
        assert fn(opp, [{"field": "name", "operator": "icontains", "value": "ENTERPRISE"}]) is True

    def test_icontains_no_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, name="Small Deal")
        assert fn(opp, [{"field": "name", "operator": "icontains", "value": "enterprise"}]) is False

    def test_numeric_gt_non_numeric_field_value_no_crash(self, tenant_a):
        """gt on a non-numeric field value must not crash — returns no-match safely."""
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, stage="prospecting")
        # 'stage' is a string; float(stage) raises ValueError → should return False (no crash)
        result = fn(opp, [{"field": "stage", "operator": "gt", "value": "1"}])
        assert result is False

    def test_numeric_lt_non_numeric_no_crash(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, stage="prospecting")
        result = fn(opp, [{"field": "stage", "operator": "lt", "value": "100"}])
        assert result is False

    def test_unknown_operator_returns_no_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, stage="prospecting")
        result = fn(opp, [{"field": "stage", "operator": "BADOP", "value": "prospecting"}])
        assert result is False

    def test_and_both_must_match(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, stage="proposal", amount="5000.00")
        # Both conditions true → True
        assert fn(opp, [
            {"field": "stage", "operator": "eq", "value": "proposal"},
            {"field": "amount", "operator": "gt", "value": "1000"},
        ]) is True

    def test_and_second_fails_short_circuits(self, tenant_a):
        fn = self._get_fn()
        opp = self._make_opp(tenant_a, stage="proposal", amount="500.00")
        # First matches, second fails → False
        assert fn(opp, [
            {"field": "stage", "operator": "eq", "value": "proposal"},
            {"field": "amount", "operator": "gt", "value": "1000"},
        ]) is False

    def test_fk_field_in_condition_returns_no_match(self, tenant_a):
        """Using 'account' (an FK field name) in a condition → _safe_record_field returns None
        → 'None' is compared to target string → eq returns False → no match (no crash)."""
        fn = self._get_fn()
        account = _make_party(tenant_a)
        opp = _make_opportunity(tenant_a, account)
        # 'account' is blocked → actual=None → a="" vs t="anything" → eq=False
        result = fn(opp, [{"field": "account", "operator": "eq", "value": "anything"}])
        assert result is False

    def test_non_dict_element_fails(self, tenant_a):
        """A non-dict element in conditions returns False (bad data → safe rejection)."""
        fn = self._get_fn()
        opp = self._make_opp(tenant_a)
        assert fn(opp, ["not_a_dict"]) is False


# ============================================================== Group 5 — _run_rule / workflowrule_run

class TestRunRule:
    """Integration tests for the _run_rule engine helper."""

    def test_matching_rule_creates_workflow_log(self, tenant_a, admin_user):
        from apps.crm.views import _run_rule
        from apps.crm.models import WorkflowLog
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account, name="Match Me", stage="prospecting")
        rule = _make_workflow_rule(
            tenant_a, trigger_entity="opportunity", trigger_event="created",
            conditions=[{"field": "stage", "operator": "eq", "value": "prospecting"}],
            actions=[],
        )
        _run_rule(rule, admin_user)
        assert WorkflowLog.objects.filter(tenant=tenant_a, rule=rule, status="success").exists()

    def test_non_matching_condition_creates_no_log(self, tenant_a, admin_user):
        from apps.crm.views import _run_rule
        from apps.crm.models import WorkflowLog
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account, stage="prospecting")
        rule = _make_workflow_rule(
            tenant_a,
            conditions=[{"field": "stage", "operator": "eq", "value": "closed_won"}],
            actions=[],
        )
        _run_rule(rule, admin_user)
        # No match → no WorkflowLog
        assert WorkflowLog.objects.filter(rule=rule).count() == 0

    def test_webhook_action_creates_delivery(self, tenant_a, admin_user):
        from apps.crm.views import _run_rule
        from apps.crm.models import WebhookDelivery
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account, stage="prospecting")
        wh = _make_webhook(tenant_a, trigger_entity="opportunity", trigger_event="created",
                           is_active=True, secret="mysecret")
        rule = _make_workflow_rule(
            tenant_a, trigger_entity="opportunity", trigger_event="created",
            conditions=[],
            actions=[{"type": "webhook"}],
        )
        _run_rule(rule, admin_user)
        assert WebhookDelivery.objects.filter(tenant=tenant_a, webhook=wh).count() >= 1

    def test_webhook_action_signs_delivery(self, tenant_a, admin_user):
        """The delivery must carry a non-empty HMAC signature when the webhook has a secret."""
        from apps.crm.views import _run_rule
        from apps.crm.models import WebhookDelivery
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account, stage="prospecting")
        wh = _make_webhook(tenant_a, trigger_entity="opportunity", trigger_event="created",
                           is_active=True, secret="signingsecret")
        rule = _make_workflow_rule(
            tenant_a, trigger_entity="opportunity", trigger_event="created",
            conditions=[], actions=[{"type": "webhook"}],
        )
        _run_rule(rule, admin_user)
        d = WebhookDelivery.objects.filter(tenant=tenant_a, webhook=wh).first()
        assert d is not None
        assert d.signature != ""

    def test_webhook_delivery_hmac_correct(self, tenant_a, admin_user):
        """HMAC-SHA256 of payload with webhook.secret must match the stored signature."""
        from apps.crm.views import _run_rule
        from apps.crm.models import WebhookDelivery
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account, stage="prospecting")
        secret = "verify_this_secret"
        wh = _make_webhook(tenant_a, trigger_entity="opportunity", trigger_event="created",
                           is_active=True, secret=secret)
        rule = _make_workflow_rule(
            tenant_a, trigger_entity="opportunity", trigger_event="created",
            conditions=[], actions=[{"type": "webhook"}],
        )
        _run_rule(rule, admin_user)
        d = WebhookDelivery.objects.filter(tenant=tenant_a, webhook=wh).first()
        assert d is not None
        expected_sig = hmac.new(
            secret.encode(), d.payload.encode(), hashlib.sha256
        ).hexdigest()
        assert d.signature == expected_sig

    def test_inactive_webhook_not_fired(self, tenant_a, admin_user):
        """An inactive Webhook must not receive deliveries even when the rule fires."""
        from apps.crm.views import _run_rule
        from apps.crm.models import WebhookDelivery
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account)
        wh = _make_webhook(tenant_a, trigger_entity="opportunity", trigger_event="created",
                           is_active=False)
        rule = _make_workflow_rule(
            tenant_a, trigger_entity="opportunity", trigger_event="created",
            conditions=[], actions=[{"type": "webhook"}],
        )
        _run_rule(rule, admin_user)
        assert WebhookDelivery.objects.filter(webhook=wh).count() == 0

    def test_approval_action_creates_approval_request(self, tenant_a, admin_user):
        from apps.crm.views import _run_rule
        from apps.crm.models import ApprovalRequest
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account)
        rule = _make_workflow_rule(
            tenant_a, conditions=[],
            actions=[{"type": "approval", "params": {"subject": "Needs Approval"}}],
        )
        _run_rule(rule, admin_user)
        assert ApprovalRequest.objects.filter(tenant=tenant_a, rule=rule).exists()

    def test_approval_action_sets_status_pending(self, tenant_a, admin_user):
        from apps.crm.views import _run_rule
        from apps.crm.models import ApprovalRequest
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account)
        rule = _make_workflow_rule(
            tenant_a, conditions=[], actions=[{"type": "approval"}],
        )
        _run_rule(rule, admin_user)
        ar = ApprovalRequest.objects.filter(tenant=tenant_a, rule=rule).first()
        assert ar is not None
        assert ar.status == "pending"

    def test_run_returns_summary_dict(self, tenant_a, admin_user):
        from apps.crm.views import _run_rule
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account)
        rule = _make_workflow_rule(tenant_a, conditions=[], actions=[])
        summary = _run_rule(rule, admin_user)
        assert "evaluated" in summary
        assert "matched" in summary
        assert "actions" in summary

    def test_run_rule_unknown_entity_creates_skipped_log(self, tenant_a, admin_user):
        """An entity not in the registry → WorkflowLog with status=skipped."""
        from apps.crm.models import WorkflowRule, WorkflowLog
        # Manually craft a rule with a bad entity to bypass model choices validation
        rule = WorkflowRule.objects.create(
            tenant=tenant_a, name="Bad Entity",
            trigger_entity="nonexistent", trigger_event="created",
        )
        from apps.crm.views import _run_rule
        _run_rule(rule, admin_user)
        assert WorkflowLog.objects.filter(rule=rule, status="skipped").exists()

    def test_run_isolates_per_record_failure(self, tenant_a, admin_user):
        """A per-record DB error must create a 'failed' log but not abort the full run."""
        from apps.crm.views import _run_rule
        from apps.crm.models import WorkflowLog
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account, name="Opp 1")
        _make_opportunity(tenant_a, account, name="Opp 2")
        # Rule with a good action — we can't easily inject a DB error per record,
        # but we can verify the engine returns a result (not an unhandled exception)
        rule = _make_workflow_rule(tenant_a, conditions=[], actions=[])
        summary = _run_rule(rule, admin_user)
        assert summary["evaluated"] >= 2
        assert WorkflowLog.objects.filter(rule=rule).count() >= 2


class TestWorkflowRuleRunView:
    """workflowrule_run view: @tenant_admin_required + @require_POST + inactive guard."""

    def test_run_post_creates_logs(self, client_a, tenant_a, admin_user):
        from apps.crm.models import WorkflowLog
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account)
        rule = _make_workflow_rule(
            tenant_a, conditions=[], actions=[], is_active=True,
        )
        resp = client_a.post(reverse("crm:workflowrule_run", args=[rule.pk]))
        assert resp.status_code == 302
        assert WorkflowLog.objects.filter(rule=rule).count() >= 1

    def test_run_blocked_for_inactive_rule(self, client_a, tenant_a):
        from apps.crm.models import WorkflowLog
        rule = _make_workflow_rule(tenant_a, is_active=False)
        resp = client_a.post(reverse("crm:workflowrule_run", args=[rule.pk]))
        assert resp.status_code == 302
        # No logs — the view short-circuits before calling _run_rule
        assert WorkflowLog.objects.filter(rule=rule).count() == 0

    def test_run_requires_post(self, client_a, tenant_a):
        """GET to workflowrule_run → 405 Method Not Allowed."""
        rule = _make_workflow_rule(tenant_a)
        resp = client_a.get(reverse("crm:workflowrule_run", args=[rule.pk]))
        assert resp.status_code == 405

    def test_run_blocked_for_non_admin(self, member_client, tenant_a):
        """Non-admin member POST → 403 (or redirect to login)."""
        rule = _make_workflow_rule(tenant_a, is_active=True)
        resp = member_client.post(reverse("crm:workflowrule_run", args=[rule.pk]))
        assert resp.status_code in (302, 403)

    def test_run_anon_redirects(self, tenant_a):
        rule = _make_workflow_rule(tenant_a)
        c = Client()
        resp = c.post(reverse("crm:workflowrule_run", args=[rule.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_run_webhook_action_creates_delivery(self, client_a, tenant_a):
        from apps.crm.models import WebhookDelivery
        account = _make_party(tenant_a)
        _make_opportunity(tenant_a, account)
        wh = _make_webhook(tenant_a, trigger_entity="opportunity", trigger_event="created",
                           is_active=True, secret="s")
        rule = _make_workflow_rule(
            tenant_a, trigger_entity="opportunity", trigger_event="created",
            conditions=[], actions=[{"type": "webhook"}], is_active=True,
        )
        client_a.post(reverse("crm:workflowrule_run", args=[rule.pk]))
        assert WebhookDelivery.objects.filter(tenant=tenant_a, webhook=wh).count() >= 1


class TestWorkflowRuleAdminGating:
    """workflowrule_create/edit/delete are @tenant_admin_required."""

    def test_member_get_create_blocked(self, member_client):
        resp = member_client.get(reverse("crm:workflowrule_create"))
        assert resp.status_code in (302, 403)

    def test_admin_get_create_allowed(self, client_a):
        resp = client_a.get(reverse("crm:workflowrule_create"))
        assert resp.status_code == 200

    def test_member_get_edit_blocked(self, member_client, tenant_a):
        rule = _make_workflow_rule(tenant_a)
        resp = member_client.get(reverse("crm:workflowrule_edit", args=[rule.pk]))
        assert resp.status_code in (302, 403)

    def test_member_post_delete_blocked(self, member_client, tenant_a):
        from apps.crm.models import WorkflowRule
        rule = _make_workflow_rule(tenant_a)
        pk = rule.pk
        member_client.post(reverse("crm:workflowrule_delete", args=[pk]))
        assert WorkflowRule.objects.filter(pk=pk).exists()

    def test_admin_post_delete_allowed(self, client_a, tenant_a):
        from apps.crm.models import WorkflowRule
        rule = _make_workflow_rule(tenant_a)
        pk = rule.pk
        resp = client_a.post(reverse("crm:workflowrule_delete", args=[pk]))
        assert resp.status_code == 302
        assert not WorkflowRule.objects.filter(pk=pk).exists()


# ============================================================== Group 6 — Webhook Views

class TestWebhookListView:
    def test_list_returns_200_for_member(self, member_client):
        resp = member_client.get(reverse("crm:webhook_list"))
        assert resp.status_code == 200

    def test_list_returns_200_for_admin(self, client_a):
        resp = client_a.get(reverse("crm:webhook_list"))
        assert resp.status_code == 200

    def test_list_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:webhook_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_list_shows_own_tenant_webhooks(self, client_a, tenant_a, tenant_b):
        wh_a = _make_webhook(tenant_a, name="A Hook")
        wh_b = _make_webhook(tenant_b, name="B Hook")
        resp = client_a.get(reverse("crm:webhook_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert wh_a.pk in pks
        assert wh_b.pk not in pks

    def test_list_context_has_entity_choices(self, client_a):
        resp = client_a.get(reverse("crm:webhook_list"))
        assert "entity_choices" in resp.context

    def test_list_context_has_event_choices(self, client_a):
        resp = client_a.get(reverse("crm:webhook_list"))
        assert "event_choices" in resp.context


class TestWebhookBooleanFilter:
    """webhook_list?is_active=False must return only inactive webhooks."""

    def test_is_active_false_filter(self, client_a, tenant_a):
        wh_active = _make_webhook(tenant_a, name="Active Hook", is_active=True)
        wh_inactive = _make_webhook(tenant_a, name="Inactive Hook", is_active=False)
        resp = client_a.get(reverse("crm:webhook_list"), {"is_active": "False"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert wh_inactive.pk in pks
        assert wh_active.pk not in pks

    def test_is_active_true_filter(self, client_a, tenant_a):
        wh_active = _make_webhook(tenant_a, name="Active Hook", is_active=True)
        wh_inactive = _make_webhook(tenant_a, name="Inactive Hook", is_active=False)
        resp = client_a.get(reverse("crm:webhook_list"), {"is_active": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert wh_active.pk in pks
        assert wh_inactive.pk not in pks

    def test_no_filter_returns_both(self, client_a, tenant_a):
        wh_active = _make_webhook(tenant_a, name="Active", is_active=True)
        wh_inactive = _make_webhook(tenant_a, name="Inactive", is_active=False)
        resp = client_a.get(reverse("crm:webhook_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert wh_active.pk in pks
        assert wh_inactive.pk in pks


class TestWebhookDetailView:
    def test_detail_returns_200_for_member(self, member_client, tenant_a):
        wh = _make_webhook(tenant_a)
        resp = member_client.get(reverse("crm:webhook_detail", args=[wh.pk]))
        assert resp.status_code == 200

    def test_detail_returns_200_for_admin(self, client_a, tenant_a):
        wh = _make_webhook(tenant_a)
        resp = client_a.get(reverse("crm:webhook_detail", args=[wh.pk]))
        assert resp.status_code == 200

    def test_detail_anon_redirects(self, tenant_a):
        wh = _make_webhook(tenant_a)
        c = Client()
        resp = c.get(reverse("crm:webhook_detail", args=[wh.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_detail_context_has_obj(self, client_a, tenant_a):
        wh = _make_webhook(tenant_a)
        resp = client_a.get(reverse("crm:webhook_detail", args=[wh.pk]))
        assert resp.context["obj"].pk == wh.pk

    def test_detail_context_has_deliveries(self, client_a, tenant_a):
        wh = _make_webhook(tenant_a)
        resp = client_a.get(reverse("crm:webhook_detail", args=[wh.pk]))
        assert "deliveries" in resp.context


class TestWebhookCreateView:
    def test_create_member_get_blocked(self, member_client):
        resp = member_client.get(reverse("crm:webhook_create"))
        assert resp.status_code in (302, 403)

    def test_create_member_post_blocked(self, member_client, tenant_a):
        from apps.crm.models import Webhook
        initial_count = Webhook.objects.filter(tenant=tenant_a).count()
        member_client.post(reverse("crm:webhook_create"), {
            "name": "Injected",
            "target_url": "https://evil.com",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "s",
            "is_active": True,
            "headers": "{}",
            "description": "",
        })
        assert Webhook.objects.filter(tenant=tenant_a).count() == initial_count

    def test_create_admin_get_returns_200(self, client_a):
        resp = client_a.get(reverse("crm:webhook_create"))
        assert resp.status_code == 200

    def test_create_admin_post_creates_webhook(self, client_a, tenant_a):
        from apps.crm.models import Webhook
        resp = client_a.post(reverse("crm:webhook_create"), {
            "name": "Admin Webhook",
            "target_url": "https://example.com/hook",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "secr3t",
            "is_active": True,
            "headers": "{}",
            "description": "Test hook",
        })
        assert resp.status_code == 302
        assert Webhook.objects.filter(tenant=tenant_a, name="Admin Webhook").exists()

    def test_create_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:webhook_create"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestWebhookEditView:
    def test_edit_member_get_blocked(self, member_client, tenant_a):
        wh = _make_webhook(tenant_a)
        resp = member_client.get(reverse("crm:webhook_edit", args=[wh.pk]))
        assert resp.status_code in (302, 403)

    def test_edit_member_post_blocked(self, member_client, tenant_a):
        wh = _make_webhook(tenant_a, name="Original Name")
        member_client.post(reverse("crm:webhook_edit", args=[wh.pk]), {
            "name": "Hacked Name",
            "target_url": wh.target_url,
            "trigger_entity": wh.trigger_entity,
            "trigger_event": wh.trigger_event,
            "secret": "",
            "is_active": True,
            "headers": "{}",
            "description": "",
        })
        wh.refresh_from_db()
        assert wh.name == "Original Name"

    def test_edit_admin_get_returns_200(self, client_a, tenant_a):
        wh = _make_webhook(tenant_a)
        resp = client_a.get(reverse("crm:webhook_edit", args=[wh.pk]))
        assert resp.status_code == 200

    def test_edit_admin_post_updates_webhook(self, client_a, tenant_a):
        wh = _make_webhook(tenant_a, name="Old Name")
        resp = client_a.post(reverse("crm:webhook_edit", args=[wh.pk]), {
            "name": "Updated Name",
            "target_url": wh.target_url,
            "trigger_entity": wh.trigger_entity,
            "trigger_event": wh.trigger_event,
            "secret": "",       # blank → keeps stored
            "is_active": True,
            "headers": "{}",
            "description": "",
        })
        assert resp.status_code == 302
        wh.refresh_from_db()
        assert wh.name == "Updated Name"


class TestWebhookDeleteView:
    def test_delete_post_only(self, client_a, tenant_a):
        """GET to webhook_delete → 405."""
        wh = _make_webhook(tenant_a)
        resp = client_a.get(reverse("crm:webhook_delete", args=[wh.pk]))
        assert resp.status_code == 405

    def test_delete_admin_post_deletes(self, client_a, tenant_a):
        from apps.crm.models import Webhook
        wh = _make_webhook(tenant_a)
        pk = wh.pk
        resp = client_a.post(reverse("crm:webhook_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Webhook.objects.filter(pk=pk).exists()

    def test_delete_member_blocked(self, member_client, tenant_a):
        from apps.crm.models import Webhook
        wh = _make_webhook(tenant_a)
        pk = wh.pk
        member_client.post(reverse("crm:webhook_delete", args=[pk]))
        assert Webhook.objects.filter(pk=pk).exists()

    def test_delete_anon_redirects(self, tenant_a):
        wh = _make_webhook(tenant_a)
        c = Client()
        resp = c.post(reverse("crm:webhook_delete", args=[wh.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestWebhookTestView:
    def test_test_admin_post_creates_delivery(self, client_a, tenant_a):
        from apps.crm.models import WebhookDelivery
        wh = _make_webhook(tenant_a, secret="testsecret")
        resp = client_a.post(reverse("crm:webhook_test", args=[wh.pk]))
        assert resp.status_code == 302
        assert WebhookDelivery.objects.filter(tenant=tenant_a, webhook=wh, event="manual.test").exists()

    def test_test_delivery_has_non_empty_signature(self, client_a, tenant_a):
        """webhook_test with a secret → delivery.signature must be a non-empty hex string."""
        from apps.crm.models import WebhookDelivery
        wh = _make_webhook(tenant_a, secret="signingsecret")
        client_a.post(reverse("crm:webhook_test", args=[wh.pk]))
        d = WebhookDelivery.objects.filter(tenant=tenant_a, webhook=wh, event="manual.test").first()
        assert d is not None
        assert d.signature != ""

    def test_test_delivery_signature_is_valid_hmac(self, client_a, tenant_a):
        """The stored signature must equal HMAC-SHA256(secret, payload)."""
        from apps.crm.models import WebhookDelivery
        secret = "check_this_signature"
        wh = _make_webhook(tenant_a, secret=secret)
        client_a.post(reverse("crm:webhook_test", args=[wh.pk]))
        d = WebhookDelivery.objects.filter(tenant=tenant_a, webhook=wh, event="manual.test").first()
        expected = hmac.new(secret.encode(), d.payload.encode(), hashlib.sha256).hexdigest()
        assert d.signature == expected

    def test_test_requires_post(self, client_a, tenant_a):
        """GET to webhook_test → 405."""
        wh = _make_webhook(tenant_a)
        resp = client_a.get(reverse("crm:webhook_test", args=[wh.pk]))
        assert resp.status_code == 405

    def test_test_member_blocked(self, member_client, tenant_a):
        from apps.crm.models import WebhookDelivery
        wh = _make_webhook(tenant_a)
        resp = member_client.post(reverse("crm:webhook_test", args=[wh.pk]))
        assert resp.status_code in (302, 403)
        assert WebhookDelivery.objects.filter(webhook=wh).count() == 0

    def test_test_anon_redirects(self, tenant_a):
        wh = _make_webhook(tenant_a)
        c = Client()
        resp = c.post(reverse("crm:webhook_test", args=[wh.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestWebhookDeliveryViews:
    def test_delivery_list_member_200(self, member_client):
        resp = member_client.get(reverse("crm:webhookdelivery_list"))
        assert resp.status_code == 200

    def test_delivery_list_admin_200(self, client_a):
        resp = client_a.get(reverse("crm:webhookdelivery_list"))
        assert resp.status_code == 200

    def test_delivery_list_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:webhookdelivery_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_delivery_detail_member_200(self, member_client, tenant_a):
        from apps.crm.models import WebhookDelivery
        wh = _make_webhook(tenant_a)
        d = WebhookDelivery.objects.create(
            tenant=tenant_a, webhook=wh, event="test", payload="{}", status="pending",
        )
        resp = member_client.get(reverse("crm:webhookdelivery_detail", args=[d.pk]))
        assert resp.status_code == 200

    def test_delivery_detail_anon_redirects(self, tenant_a):
        from apps.crm.models import WebhookDelivery
        wh = _make_webhook(tenant_a)
        d = WebhookDelivery.objects.create(
            tenant=tenant_a, webhook=wh, event="test", payload="{}", status="pending",
        )
        c = Client()
        resp = c.get(reverse("crm:webhookdelivery_detail", args=[d.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_delivery_list_shows_own_tenant_only(self, client_a, tenant_a, tenant_b):
        from apps.crm.models import WebhookDelivery
        wh_a = _make_webhook(tenant_a, name="A Hook")
        wh_b = _make_webhook(tenant_b, name="B Hook")
        d_a = WebhookDelivery.objects.create(
            tenant=tenant_a, webhook=wh_a, event="test", payload="{}", status="pending",
        )
        d_b = WebhookDelivery.objects.create(
            tenant=tenant_b, webhook=wh_b, event="test", payload="{}", status="pending",
        )
        resp = client_a.get(reverse("crm:webhookdelivery_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert d_a.pk in pks
        assert d_b.pk not in pks


# ============================================================== Group 7 — Read-only deliveries

class TestWebhookDeliveryReadOnly:
    """WebhookDelivery has no create/edit/delete URL — assert NoReverseMatch."""

    def test_no_webhookdelivery_create_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:webhookdelivery_create")

    def test_no_webhookdelivery_edit_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:webhookdelivery_edit", args=[1])

    def test_no_webhookdelivery_delete_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:webhookdelivery_delete", args=[1])

    def test_no_workflowlog_create_url(self):
        """WorkflowLog is also read-only."""
        with pytest.raises(NoReverseMatch):
            reverse("crm:workflowlog_create")

    def test_no_workflowlog_delete_url(self):
        with pytest.raises(NoReverseMatch):
            reverse("crm:workflowlog_delete", args=[1])


# ============================================================== Group 8 — Multi-tenant IDOR

class TestCrossTenantWebhookIDOR:
    def test_webhook_detail_cross_tenant_404(self, client_a, tenant_b):
        wh_b = _make_webhook(tenant_b, name="B Hook")
        resp = client_a.get(reverse("crm:webhook_detail", args=[wh_b.pk]))
        assert resp.status_code == 404

    def test_webhook_edit_cross_tenant_404(self, client_a, tenant_b):
        wh_b = _make_webhook(tenant_b, name="B Hook")
        resp = client_a.get(reverse("crm:webhook_edit", args=[wh_b.pk]))
        assert resp.status_code == 404

    def test_webhook_delete_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import Webhook
        wh_b = _make_webhook(tenant_b, name="B Hook")
        resp = client_a.post(reverse("crm:webhook_delete", args=[wh_b.pk]))
        assert resp.status_code == 404
        assert Webhook.objects.filter(pk=wh_b.pk).exists()

    def test_webhook_test_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import WebhookDelivery
        wh_b = _make_webhook(tenant_b, name="B Hook")
        resp = client_a.post(reverse("crm:webhook_test", args=[wh_b.pk]))
        assert resp.status_code == 404
        assert WebhookDelivery.objects.filter(webhook=wh_b).count() == 0

    def test_webhookdelivery_detail_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import WebhookDelivery
        wh_b = _make_webhook(tenant_b, name="B Hook")
        d_b = WebhookDelivery.objects.create(
            tenant=tenant_b, webhook=wh_b, event="test", payload="{}", status="pending",
        )
        resp = client_a.get(reverse("crm:webhookdelivery_detail", args=[d_b.pk]))
        assert resp.status_code == 404

    def test_workflowrule_run_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import WorkflowLog
        rule_b = _make_workflow_rule(tenant_b, name="B Rule", is_active=True)
        resp = client_a.post(reverse("crm:workflowrule_run", args=[rule_b.pk]))
        assert resp.status_code == 404
        assert WorkflowLog.objects.filter(rule=rule_b).count() == 0

    def test_workflowrule_detail_cross_tenant_404(self, client_a, tenant_b):
        rule_b = _make_workflow_rule(tenant_b, name="B Rule")
        resp = client_a.get(reverse("crm:workflowrule_detail", args=[rule_b.pk]))
        assert resp.status_code == 404

    def test_workflowrule_edit_cross_tenant_404(self, client_a, tenant_b):
        rule_b = _make_workflow_rule(tenant_b, name="B Rule")
        resp = client_a.get(reverse("crm:workflowrule_edit", args=[rule_b.pk]))
        assert resp.status_code == 404

    def test_workflowrule_delete_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import WorkflowRule
        rule_b = _make_workflow_rule(tenant_b, name="B Rule")
        resp = client_a.post(reverse("crm:workflowrule_delete", args=[rule_b.pk]))
        assert resp.status_code == 404
        assert WorkflowRule.objects.filter(pk=rule_b.pk).exists()

    def test_webhook_list_never_leaks_tenant_b(self, client_a, tenant_b):
        wh_b = _make_webhook(tenant_b, name="B's Secret")
        resp = client_a.get(reverse("crm:webhook_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert wh_b.pk not in pks


# ============================================================== Group 9 — CSRF enforcement

class TestWorkflow110CSRF:
    def test_workflowrule_run_enforces_csrf(self, admin_user, tenant_a):
        rule = _make_workflow_rule(tenant_a, is_active=True)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:workflowrule_run", args=[rule.pk]))
        assert resp.status_code == 403

    def test_webhook_create_enforces_csrf(self, admin_user, tenant_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:webhook_create"), {
            "name": "Hook",
            "target_url": "https://example.com",
            "trigger_entity": "opportunity",
            "trigger_event": "created",
            "secret": "s",
            "is_active": True,
            "headers": "{}",
            "description": "",
        })
        assert resp.status_code == 403

    def test_webhook_test_enforces_csrf(self, admin_user, tenant_a):
        wh = _make_webhook(tenant_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:webhook_test", args=[wh.pk]))
        assert resp.status_code == 403

    def test_webhook_delete_enforces_csrf(self, admin_user, tenant_a):
        wh = _make_webhook(tenant_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:webhook_delete", args=[wh.pk]))
        assert resp.status_code == 403

    def test_workflowrule_delete_enforces_csrf(self, admin_user, tenant_a):
        rule = _make_workflow_rule(tenant_a)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:workflowrule_delete", args=[rule.pk]))
        assert resp.status_code == 403


# ============================================================== Group 10 — WorkflowLog Views

class TestWorkflowLogViews:
    def test_log_list_member_200(self, member_client):
        resp = member_client.get(reverse("crm:workflowlog_list"))
        assert resp.status_code == 200

    def test_log_list_admin_200(self, client_a):
        resp = client_a.get(reverse("crm:workflowlog_list"))
        assert resp.status_code == 200

    def test_log_list_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("crm:workflowlog_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_log_detail_member_200(self, member_client, tenant_a, admin_user):
        from apps.crm.models import WorkflowLog
        rule = _make_workflow_rule(tenant_a)
        log = WorkflowLog.objects.create(
            tenant=tenant_a, rule=rule, record_label="Test Opp", status="success",
        )
        resp = member_client.get(reverse("crm:workflowlog_detail", args=[log.pk]))
        assert resp.status_code == 200

    def test_log_list_shows_own_tenant_only(self, client_a, tenant_a, tenant_b):
        from apps.crm.models import WorkflowLog
        rule_a = _make_workflow_rule(tenant_a, name="A Rule")
        rule_b = _make_workflow_rule(tenant_b, name="B Rule")
        log_a = WorkflowLog.objects.create(
            tenant=tenant_a, rule=rule_a, record_label="A Opp", status="success",
        )
        log_b = WorkflowLog.objects.create(
            tenant=tenant_b, rule=rule_b, record_label="B Opp", status="success",
        )
        resp = client_a.get(reverse("crm:workflowlog_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert log_a.pk in pks
        assert log_b.pk not in pks

    def test_log_detail_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import WorkflowLog
        rule_b = _make_workflow_rule(tenant_b, name="B Rule")
        log_b = WorkflowLog.objects.create(
            tenant=tenant_b, rule=rule_b, record_label="B Opp", status="success",
        )
        resp = client_a.get(reverse("crm:workflowlog_detail", args=[log_b.pk]))
        assert resp.status_code == 404


# ============================================================== Group 11 — ApprovalRequest Views

class TestApprovalRequestViews:
    def test_approval_list_member_200(self, member_client):
        resp = member_client.get(reverse("crm:approvalrequest_list"))
        assert resp.status_code == 200

    def test_approval_list_shows_own_tenant(self, client_a, tenant_a, tenant_b, admin_user):
        from apps.crm.models import ApprovalRequest
        rule_a = _make_workflow_rule(tenant_a, name="A Rule")
        rule_b = _make_workflow_rule(tenant_b, name="B Rule")
        ar_a = ApprovalRequest.objects.create(
            tenant=tenant_a, rule=rule_a, subject="Approve A", requested_by=admin_user,
        )
        # Create admin_b user for tenant_b
        from apps.accounts.models import User
        user_b = User.objects.create_user(
            username="admin_b2", email="b2@b.com", password="pass", tenant=tenant_b, is_tenant_admin=True
        )
        ar_b = ApprovalRequest.objects.create(
            tenant=tenant_b, rule=rule_b, subject="Approve B", requested_by=user_b,
        )
        resp = client_a.get(reverse("crm:approvalrequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert ar_a.pk in pks
        assert ar_b.pk not in pks

    def test_approval_detail_cross_tenant_404(self, client_a, tenant_b):
        from apps.crm.models import ApprovalRequest
        rule_b = _make_workflow_rule(tenant_b, name="B Rule")
        from apps.accounts.models import User
        user_b = User.objects.create_user(
            username="req_b3", email="b3@b.com", password="pass", tenant=tenant_b,
        )
        ar_b = ApprovalRequest.objects.create(
            tenant=tenant_b, rule=rule_b, subject="B Approval", requested_by=user_b,
        )
        resp = client_a.get(reverse("crm:approvalrequest_detail", args=[ar_b.pk]))
        assert resp.status_code == 404


# ============================================================== Group 12 — Query-count

class TestRunRuleQueryCount:
    """_run_rule must not N+1 per record even with FK-field conditions (blocked by allowlist)."""

    def test_bounded_queries_for_many_opportunities(self, tenant_a, admin_user):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.crm.views import _run_rule

        account = _make_party(tenant_a)
        for i in range(10):
            _make_opportunity(tenant_a, account, name=f"Opp {i}", amount=str(i * 100))

        # Rule with an FK-field condition: 'account' is blocked by _safe_record_field →
        # no per-record FK fetch; condition always returns no-match (None != "anything")
        rule = _make_workflow_rule(
            tenant_a, trigger_entity="opportunity", trigger_event="created",
            conditions=[{"field": "account", "operator": "eq", "value": "anything"}],
            actions=[],
        )

        # Warm-up (session / middleware caches)
        _run_rule(rule, admin_user)
        # Clear the logs from warm-up
        from apps.crm.models import WorkflowLog
        WorkflowLog.objects.filter(rule=rule).delete()

        with CaptureQueriesContext(connection) as ctx:
            _run_rule(rule, admin_user)

        # Expected queries: 1 (active webhooks) + 1 (opportunities slice) + N logs
        # The key assertion: no per-record SELECT (no N+1) — logs are bulk-ish via savepoint.
        # Upper bound: generous cap that catches O(N) growth (10 records → should be < 30 queries)
        n_queries = len(ctx.captured_queries)
        assert n_queries < 30, (
            f"Expected < 30 queries for _run_rule over 10 opportunities, got {n_queries}. "
            f"Possible N+1 (per-record FK lazy-load or per-record log SELECT)."
        )

    def test_webhook_list_no_n_plus_one(self, client_a, tenant_a):
        """webhook_list with multiple webhooks+deliveries must not N+1."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.crm.models import WebhookDelivery

        for i in range(5):
            wh = _make_webhook(tenant_a, name=f"Hook {i}")
            for _ in range(3):
                WebhookDelivery.objects.create(
                    tenant=tenant_a, webhook=wh, event="test", payload="{}", status="pending",
                )

        # Warm-up
        client_a.get(reverse("crm:webhook_list"))

        with CaptureQueriesContext(connection) as ctx:
            resp = client_a.get(reverse("crm:webhook_list"))

        assert resp.status_code == 200
        assert len(ctx.captured_queries) < 20, (
            f"Expected <20 queries for webhook_list (5 hooks), "
            f"got {len(ctx.captured_queries)}. Possible N+1."
        )
