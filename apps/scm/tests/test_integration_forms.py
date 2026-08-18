"""SCM 4.19 Integration & API Gateway — FORM tests.

This lane owns the form boundary and nothing else (the models, views and security lanes own the
rest). 4.19 ships exactly TWO ModelForms — ``IntegrationEndpointForm`` and
``WebhookSubscriptionForm`` — and the absence of the other two is itself a decision this file
asserts: ``IntegrationMessage`` and ``WebhookDelivery`` are APPEND-ONLY logs with no form, no
create/edit/delete route and no module under ``apps/scm/forms/IntegrationApiGateway/``.

Four questions are asked here:

1. **What is on a form, and what must never be.** Both ``Meta.fields`` whitelists are pinned exactly
   (22 and 11 names, in declaration order), so a field added to — or dropped from — either form is a
   FAILURE rather than a silent change. Every exclusion is then asserted BY REASON: ``tenant``
   (stamped by ``TenantUniqueMixin.__init__`` before validation and by ``crud_create`` after it), the
   auto numbers (``CNX-#####`` / ``WHK-#####``, minted in ``TenantNumbered.save()``), **both secret
   column pairs** (``credential_prefix``/``credential_hash`` and
   ``signing_secret_prefix``/``signing_secret_hash``), the derived counter
   ``consecutive_failures``, and every system ``*_at`` timestamp (``last_run_at``,
   ``last_success_at``, ``last_seen_at``, ``last_delivery_at``, ``created_at``, ``updated_at``).

   That is L20 and L22 stated twice over, because the two lessons have different failure modes: a
   secret named in ``Meta.fields`` ships its STORED VALUE back to the browser in the bound edit
   render's ``value=""`` attribute — masking it in the template does not help, since the leak is in
   the HTML the form generates — and a system ``*_at`` on a ``DateInput`` is silently TRUNCATED to
   midnight the next time anybody saves the page. Both are asserted structurally as well as by name:
   every one of those columns is ``editable=False`` on the model, so ``modelform_factory`` REFUSES to
   build a field for it at all, and a later hand adding it to a field list gets a ``FieldError``
   rather than a working leak.

2. **The clean() rules at the boundary a user actually reaches** — the required fields, over-length
   and out-of-choice values, ``endpoint_url``'s deliberate acceptance of ``sftp://`` / ``as2://`` /
   ``mqtt://`` / ``llrp://`` against ``target_url``'s deliberate refusal of them, CONSTRAINT A (an
   interchange id typed onto a connection that already names a 3PL client), the duplicate name that
   ``TenantUniqueMixin`` turns from an uncaught ``IntegrityError`` (a 500 on a mainline CRUD path)
   into a rendered error, and ``clean_headers``' three refusals — non-dict, non-string, and a CR/LF
   that would be request splitting rather than formatting.

3. **FK ModelChoiceField querysets are tenant-scoped.** Every dropdown offered to tenant A is empty
   of tenant B rows; a tenant-less caller (the superuser has ``tenant=None`` BY DESIGN) is offered
   NOTHING rather than the unscoped default manager, which would pool every workspace into one
   ``<select>``; and ``_reject_foreign`` still refuses a foreign pk when the narrowed ``<select>`` is
   widened out from under it — a narrowed dropdown is UX, never an authorization boundary (L39 §2).

4. **The two log tables have no form at all**, asserted positively rather than by omission.

Naming: every test is ``test_integration_*`` and every module-level helper / constant / fixture
``_integration_*`` (``test_suite_hygiene.py`` parses this package and fails on any module-level name
defined twice; the prefix also protects the sub-module that appends next). Every moment derives from
``timezone.now()`` — never ``datetime.date.today()`` (L16).
"""
import importlib.util
import pathlib

import pytest
from django import forms as django_forms
from django.core.exceptions import FieldError
from django.forms import modelform_factory

pytestmark = pytest.mark.django_db


# =================================================================================================
# Module-level helpers and constants — every one prefixed `_integration_`
# =================================================================================================

#: The exact ``Meta.fields`` whitelists, in declaration order. Pinned HERE rather than read off the
#: form, so that a field added to (or removed from) either form fails this file instead of shipping.
_integration_EXPECTED_FIELDS = {
    "IntegrationEndpointForm": [
        # identity
        "name", "category", "system", "direction", "transport", "auth_method",
        "endpoint_url", "external_account_ref",
        # pointers
        "partner_party", "logistics_client", "location", "spec_document",
        # EDI / device identity (constraint A)
        "interchange_id", "interchange_qualifier", "device_identifier",
        # scheduling intent
        "trigger_mode", "schedule_note",
        # lifecycle
        "environment", "lifecycle_stage", "status", "is_active",
        "notes",
    ],
    "WebhookSubscriptionForm": [
        "name", "trigger_entity", "trigger_event", "target_url", "payload_format",
        "filter_expression", "include_fields", "headers", "auto_disable_threshold",
        "is_active", "description",
    ],
}

#: Substrings that must never appear in ANY 4.19 form field name. 4.19 is the first sub-module that
#: actually STORES credential material, which is what makes this list load-bearing rather than
#: decorative: `credential_hash` and `signing_secret_hash` are one careless `Meta.fields` entry away
#: from being rendered into an edit page (L20).
#:
#: `endpoint` and `webhook` are deliberately NOT tokens here — `endpoint_url` is a legitimate,
#: non-secret configuration column and the whole sub-module is named after webhooks.
_integration_SECRET_TOKENS = (
    "password", "passwd", "secret", "credential", "hash", "salt", "digest",
    "api_key", "apikey", "token", "private_key", "access_key", "signature", "signing",
)

#: Columns that exist on the 4.19 models and must NEVER reach a form, each named so a later hand
#: dropping `editable=False` "for admin convenience" fails here rather than in production.
_integration_FORBIDDEN_FIELDS = (
    "tenant", "number",
    # the two secret markers — rotate_credential / rotate_secret are their ONLY writers
    "credential_prefix", "credential_hash", "signing_secret_prefix", "signing_secret_hash",
    # derived counter (L29) — a counter a human can type stops meaning anything
    "consecutive_failures",
    # system timestamps (L22)
    "last_run_at", "last_success_at", "last_seen_at", "last_delivery_at",
    "created_at", "updated_at",
)

#: Every ``editable=False`` column a ModelForm must be structurally unable to reach, per model.
_integration_NON_EDITABLE_COLUMNS = {
    "IntegrationEndpoint": (
        "number", "credential_prefix", "credential_hash", "consecutive_failures",
        "last_run_at", "last_success_at", "last_seen_at",
    ),
    "WebhookSubscription": (
        "number", "signing_secret_prefix", "signing_secret_hash", "consecutive_failures",
        "last_delivery_at",
    ),
}

#: The four tenant-scoped pointers on ``IntegrationEndpoint`` — the model's own TENANT_SCOPED_FKS,
#: restated so a fifth FK added to the model without being added to that tuple is visible here.
_integration_ENDPOINT_FKS = ("partner_party", "logistics_client", "location", "spec_document")


def _integration_forms(tenant=None):
    """One UNBOUND instance of each 4.19 form, keyed by class name."""
    from apps.scm.forms import IntegrationEndpointForm, WebhookSubscriptionForm
    return {
        "IntegrationEndpointForm": IntegrationEndpointForm(tenant=tenant),
        "WebhookSubscriptionForm": WebhookSubscriptionForm(tenant=tenant),
    }


def _integration_errors_text(form):
    """Every error message on ``form`` — field AND non-field — as ONE lowercase string.

    For asserting the REASON a refusal came back, not merely that one did: a rejection carrying the
    wrong explanation is a bug the user pays for.
    """
    return " ".join(
        message for messages in form.errors.values() for message in messages).lower()


def _integration_endpoint_post(**overrides):
    """A minimal VALID ``IntegrationEndpointForm`` POST.

    ``name`` is the ONLY field the model requires — every other column is blank or defaulted — but
    a browser posts the whole form, so the realistic body is spelled out. Every value is a STRING
    because that is what a ``QueryDict`` hands a form; a test posting ``int``/``Decimal`` objects is
    testing a request shape that cannot occur.
    """
    data = {
        "name": "Partner AS2 interchange",
        "category": "edi",
        "system": "edi_van",
        "direction": "bidirectional",
        "transport": "as2",
        "auth_method": "mtls",
        "endpoint_url": "https://as2.partner.example.net/exchange",
        "external_account_ref": "",
        "partner_party": "",
        "logistics_client": "",
        "location": "",
        "spec_document": "",
        "interchange_id": "",
        "interchange_qualifier": "",
        "device_identifier": "",
        "trigger_mode": "manual",
        "schedule_note": "",
        "environment": "sandbox",
        "lifecycle_stage": "setup",
        "status": "disconnected",
        # An unchecked checkbox is simply ABSENT from a browser's body; `is_active` renders checked
        # (the model default is True), so a normal create posts it.
        "is_active": "on",
        "notes": "",
    }
    data.update(overrides)
    return {key: str(value) for key, value in data.items()}


def _integration_subscription_post(**overrides):
    """A minimal VALID ``WebhookSubscriptionForm`` POST."""
    data = {
        "name": "Notify the ERP when a goods receipt posts",
        "trigger_entity": "goods_receipt",
        "trigger_event": "posted",
        "target_url": "https://erp.example.com/hooks/goods-receipt",
        "payload_format": "json",
        "filter_expression": "",
        "include_fields": "",
        "headers": '{"X-Source": "NavERP"}',
        "auto_disable_threshold": "8",
        "is_active": "on",
        "description": "",
    }
    data.update(overrides)
    return {key: str(value) for key, value in data.items()}


def _integration_widen_fk(form, name):
    """Re-point a scoped ``ModelChoiceField`` at its model's UNSCOPED manager, in place.

    Simulates the regression that ``_reject_foreign`` exists for: somebody widens (or forgets to
    narrow) a dropdown, and the ONLY thing then standing between a crafted POST and another
    workspace's row is the ``clean()`` re-check. A narrowed ``<select>`` has never been an
    authorization boundary (L39 §2) — this makes the second boundary observable.
    """
    field = form.fields[name]
    field.queryset = field.queryset.model._default_manager.all()
    return form


def _integration_model_choice_fields(form):
    """``{name: field}`` for every ``ModelChoiceField`` on ``form``."""
    return {name: field for name, field in form.fields.items()
            if isinstance(field, django_forms.ModelChoiceField)}


# =================================================================================================
# Local fixtures — only what conftest.py does not already provide (it is FINAL and off-limits)
# =================================================================================================
@pytest.fixture
def _integration_endpoint_form(tenant_a):
    """An unbound ``IntegrationEndpointForm`` scoped to tenant_a."""
    from apps.scm.forms import IntegrationEndpointForm
    return IntegrationEndpointForm(tenant=tenant_a)


@pytest.fixture
def _integration_subscription_form(tenant_a):
    """An unbound ``WebhookSubscriptionForm`` scoped to tenant_a."""
    from apps.scm.forms import WebhookSubscriptionForm
    return WebhookSubscriptionForm(tenant=tenant_a)


# =================================================================================================
# Cross-form shape guards — L20 / L22, asked of BOTH 4.19 forms at once
# =================================================================================================
class TestIntegrationFormShapeAcrossTheSubModule:
    def test_integration_every_form_matches_its_pinned_field_whitelist(self):
        """A field added to (or dropped from) either 4.19 form is a FAILURE, not a silent change.

        Both are ``Meta.fields`` whitelists rather than ``Meta.exclude``: a whitelist fails CLOSED
        when a column is added to the model later, which is what stops a system column becoming
        user-editable by accident.
        """
        for name, form in _integration_forms().items():
            assert list(form.fields) == _integration_EXPECTED_FIELDS[name], name

    def test_integration_endpoint_form_carries_exactly_twenty_two_fields(self):
        assert len(_integration_EXPECTED_FIELDS["IntegrationEndpointForm"]) == 22
        from apps.scm.forms import IntegrationEndpointForm
        assert len(IntegrationEndpointForm(tenant=None).fields) == 22

    def test_integration_subscription_form_carries_exactly_eleven_fields(self):
        assert len(_integration_EXPECTED_FIELDS["WebhookSubscriptionForm"]) == 11
        from apps.scm.forms import WebhookSubscriptionForm
        assert len(WebhookSubscriptionForm(tenant=None).fields) == 11

    def test_integration_no_form_exposes_tenant_or_the_auto_number(self):
        """``tenant`` is stamped (``TenantUniqueMixin.__init__`` before validation, ``crud_create``
        after it) and the numbers are minted in ``TenantNumbered.save()``. Either on a form is a
        mass-assignment hole — a POST could file a row into another workspace or collide a number."""
        for name, form in _integration_forms().items():
            assert "tenant" not in form.fields, name
            assert "number" not in form.fields, name

    def test_integration_no_form_exposes_a_secret_column(self):
        """L20, the lesson 4.19 is the first sub-module able to break.

        A secret named in ``Meta.fields`` ships its STORED value in the bound edit render's
        ``value=""``. Both column pairs are absent by name here and structurally absent below.
        """
        for name, form in _integration_forms().items():
            for column in ("credential_prefix", "credential_hash",
                           "signing_secret_prefix", "signing_secret_hash"):
                assert column not in form.fields, f"{name}.{column}"

    def test_integration_no_form_field_name_looks_like_a_secret(self):
        """The same rule stated by SHAPE rather than by name, so a differently-spelled credential
        column added later ("api_token", "shared_secret") is caught too."""
        for name, form in _integration_forms().items():
            for field_name in form.fields:
                lowered = field_name.lower()
                for token in _integration_SECRET_TOKENS:
                    assert token not in lowered, f"{name}.{field_name} looks like a secret"

    def test_integration_no_form_exposes_a_system_timestamp(self):
        """L22. A ``DateTimeField`` on a ``TenantModelForm`` gets a ``DateInput`` and is silently
        TRUNCATED to midnight on the next save — so every system ``*_at`` stays ``editable=False``
        and off both forms. ``last_success_at`` above all: it is the evidence of when this
        connection last actually worked."""
        for name, form in _integration_forms().items():
            for field_name in form.fields:
                assert not field_name.endswith("_at"), f"{name}.{field_name}"

    def test_integration_no_form_exposes_a_derived_counter_or_property(self):
        """``consecutive_failures`` is DERIVED state and ``masked`` /
        ``effective_interchange_id`` / ``effective_interchange_qualifier`` /
        ``next_backoff_seconds`` are computed reads. A stored, typeable second answer goes stale by
        sitting still (L29)."""
        for name, form in _integration_forms().items():
            for field_name in ("consecutive_failures", "masked", "effective_interchange_id",
                               "effective_interchange_qualifier", "next_backoff_seconds",
                               "attempt_count", "attempt_no"):
                assert field_name not in form.fields, f"{name}.{field_name}"

    def test_integration_no_form_exposes_any_forbidden_column(self):
        """The whole forbidden list, over both forms, in one assertion."""
        for name, form in _integration_forms().items():
            for column in _integration_FORBIDDEN_FIELDS:
                assert column not in form.fields, f"{name}.{column}"

    @pytest.mark.parametrize(
        "model_name,column",
        [(model, column)
         for model, columns in _integration_NON_EDITABLE_COLUMNS.items()
         for column in columns])
    def test_integration_a_forbidden_column_cannot_be_resurrected_by_a_modelform(
            self, model_name, column):
        """The exclusions are STRUCTURAL, not a promise a field list has to keep.

        Each column is ``editable=False`` on the model, so Django refuses to build a form field for
        it: naming it in ``Meta.fields`` raises ``FieldError`` at class-construction time. That is
        strictly stronger than a whitelist — a whitelist protects the columns whoever wrote it
        remembered, ``editable=False`` protects the ones a later pass adds without reading the file.
        """
        from apps.scm import models as scm_models
        model = getattr(scm_models, model_name)
        assert model._meta.get_field(column).editable is False
        with pytest.raises(FieldError):
            modelform_factory(model, fields=[column])

    def test_integration_a_tenantless_caller_is_offered_nothing(self):
        """The superuser has ``tenant=None`` BY DESIGN. ``TenantModelForm`` only scopes a dropdown
        when a tenant is present, so ``_tenant_qs`` answers ``.none()`` instead — an empty select is
        the honest answer for a user ``crud_create`` refuses to create rows for anyway."""
        for name, form in _integration_forms(tenant=None).items():
            for field_name, field in _integration_model_choice_fields(form).items():
                assert not field.queryset.exists(), f"{name}.{field_name} leaked rows"

    def test_integration_no_tenant_a_dropdown_contains_a_tenant_b_row(
            self, tenant_a, tenant_b, supplier_a, supplier_b, tpl_client_shared_a, tpl_client_b,
            location_a, location_b, evidence_document_a, evidence_document_b):
        """The mandatory isolation assertion at the FORM boundary, over both forms at once."""
        for name, form in _integration_forms(tenant=tenant_a).items():
            for field_name, field in _integration_model_choice_fields(form).items():
                foreign = [row.pk for row in field.queryset
                           if getattr(row, "tenant_id", None) != tenant_a.pk]
                assert not foreign, f"{name}.{field_name} offered tenant_b rows {foreign}"


# =================================================================================================
# IntegrationEndpointForm — shape and widgets
# =================================================================================================
class TestIntegrationEndpointFormShape:
    def test_integration_endpoint_form_field_order_is_pinned(self, _integration_endpoint_form):
        assert list(_integration_endpoint_form.fields) == \
            _integration_EXPECTED_FIELDS["IntegrationEndpointForm"]

    def test_integration_endpoint_form_required_fields_are_name_plus_the_defaulted_choices(
            self, _integration_endpoint_form):
        """``name`` is the only column the MODEL requires — ``IntegrationEndpoint.objects.create(
        tenant=…, name='X')`` is a legal row — but the eight defaulted ``CHOICES`` columns are still
        required INPUTS on a bound form, because ``blank=False`` plus a default is Django's shape for
        "always rendered with an initial, so a browser always posts it".

        Every free-text and pointer column is genuinely optional, which is the property that matters:
        a connection can be registered before onboarding has discovered its URL, its partner or its
        interchange identity.
        """
        required = {name for name, field in _integration_endpoint_form.fields.items()
                    if field.required}
        assert required == {"name", "category", "direction", "transport", "auth_method",
                            "trigger_mode", "environment", "lifecycle_stage", "status"}
        optional = set(_integration_endpoint_form.fields) - required
        assert optional == {"system", "endpoint_url", "external_account_ref", "partner_party",
                            "logistics_client", "location", "spec_document", "interchange_id",
                            "interchange_qualifier", "device_identifier", "schedule_note",
                            "is_active", "notes"}

    def test_integration_endpoint_form_keeps_status_on_the_form_deliberately(
            self, _integration_endpoint_form):
        """4.19 ships NO transport, so nothing can observe a connection succeed or fail: there is no
        state machine to own this column and an engineer maintains it by hand. That makes it the one
        ``status`` in scm that legitimately belongs on a form — the opposite of
        ``consecutive_failures``, which is derived and excluded."""
        assert "status" in _integration_endpoint_form.fields
        values = [value for value, _label in _integration_endpoint_form.fields["status"].choices
                  if value]
        assert values == ["disconnected", "connected", "error", "disabled"]

    def test_integration_endpoint_url_widget_is_a_text_input_not_a_url_input(
            self, _integration_endpoint_form):
        """A ``URLInput`` would let the BROWSER refuse ``sftp://`` / ``as2://`` / ``mqtt://`` /
        ``llrp://`` before the request was ever sent — the exact schemes this column exists to
        hold. The model column is a ``CharField`` for the matching reason."""
        widget = _integration_endpoint_form.fields["endpoint_url"].widget
        assert isinstance(widget, django_forms.TextInput)
        assert not isinstance(widget, django_forms.URLInput)

    def test_integration_endpoint_form_widget_overrides_are_present(
            self, _integration_endpoint_form):
        fields = _integration_endpoint_form.fields
        assert isinstance(fields["schedule_note"].widget, django_forms.TextInput)
        assert isinstance(fields["notes"].widget, django_forms.Textarea)
        assert fields["notes"].widget.attrs.get("rows") == 3

    def test_integration_endpoint_form_help_texts_state_the_credential_rule(
            self, _integration_endpoint_form):
        """The one place a person filling this form will read it: no credential is typed HERE, and
        a 3PL link means the interchange pair is read through the client record."""
        assert "credential" in _integration_endpoint_form.fields["auth_method"].help_text.lower()
        assert "blank" in _integration_endpoint_form.fields["logistics_client"].help_text.lower()

    def test_integration_endpoint_form_applies_the_shared_css_classes(
            self, _integration_endpoint_form):
        """``TenantModelForm`` styles every widget; a form that skipped ``super().__init__`` would
        render unstyled controls and nothing else would notice."""
        fields = _integration_endpoint_form.fields
        assert fields["category"].widget.attrs.get("class") == "form-select"
        assert fields["name"].widget.attrs.get("class") == "form-input"
        assert fields["notes"].widget.attrs.get("class") == "form-textarea"
        assert fields["is_active"].widget.attrs.get("class") == "form-check"


# =================================================================================================
# IntegrationEndpointForm — validation
# =================================================================================================
class TestIntegrationEndpointFormValidation:
    def test_integration_endpoint_form_accepts_a_minimal_body(self, tenant_a):
        """A name plus the eight defaulted selects — nothing else. Every free-text column and all
        four pointers stay empty, and the row still saves: a connection is registrable before
        onboarding knows its URL, its counterparty or its interchange identity."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data={"name": "Bare minimum connection", "category": "custom", "direction": "inbound",
                  "transport": "manual", "auth_method": "none", "trigger_mode": "manual",
                  "environment": "sandbox", "lifecycle_stage": "setup", "status": "disconnected"},
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.endpoint_url == ""
        assert obj.partner_party_id is None
        assert obj.logistics_client_id is None
        assert obj.location_id is None
        assert obj.spec_document_id is None
        # An absent checkbox reads as UNCHECKED, never as the model default — the create page renders
        # `is_active` checked, so a body that omits it really is asking for an inactive row.
        assert obj.is_active is False

    def test_integration_endpoint_form_rejects_a_blank_name(self, tenant_a):
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(data=_integration_endpoint_post(name=""), tenant=tenant_a)
        assert not form.is_valid()
        assert set(form.errors) == {"name"}
        assert "required" in _integration_errors_text(form)

    def test_integration_endpoint_form_rejects_an_over_length_name(self, tenant_a):
        """``name`` is ``max_length=120``; 121 characters must come back as a field error rather
        than as a database truncation or a 500 on save."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(name="x" * 121), tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors

    @pytest.mark.parametrize("field,value", [
        ("category", "banana"),
        ("system", "not_a_platform"),
        ("direction", "sideways"),
        ("transport", "carrier_pigeon"),
        ("auth_method", "vibes"),
        ("trigger_mode", "whenever"),
        ("environment", "staging"),
        ("lifecycle_stage", "retired"),
        ("status", "on_fire"),
    ])
    def test_integration_endpoint_form_rejects_a_value_outside_its_choices(
            self, tenant_a, field, value):
        """Nine ``CHOICES`` columns, nine ways a crafted POST can smuggle a value the templates'
        badge conditions and the list filters were never written for."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(**{field: value}), tenant=tenant_a)
        assert not form.is_valid()
        assert field in form.errors
        assert "valid choice" in _integration_errors_text(form)

    @pytest.mark.parametrize("url", [
        "https://as2.partner.example.net/exchange",
        "sftp://sftp.partner.example.com/outbound",
        "as2://partner.example.net",
        "mqtt://broker.internal.example.com:1883/scm/telemetry",
        "llrp://10.20.4.17:5084",
        "\\\\fileserver\\edi\\drop",
    ])
    def test_integration_endpoint_url_accepts_a_non_http_scheme(self, tenant_a, url):
        """The whole point of the ``CharField``: an EDI/IoT endpoint is frequently not HTTP, and a
        ``URLField`` would reject these at ModelForm validation only — the seeder would pass and the
        UI would fail, the worst possible place to find out."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(endpoint_url=url), tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["endpoint_url"] == url

    def test_integration_endpoint_url_is_still_length_bounded(self, tenant_a):
        """Free-form is not unbounded: 501 characters is a field error, not a truncating INSERT."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(endpoint_url="https://x.example.com/" + "y" * 500),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "endpoint_url" in form.errors

    def test_integration_endpoint_form_rejects_an_over_length_interchange_id(self, tenant_a):
        """``interchange_id`` is ``max_length=32`` — an ISA sender id, not a paragraph."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(interchange_id="Z" * 33), tenant=tenant_a)
        assert not form.is_valid()
        assert "interchange_id" in form.errors

    def test_integration_endpoint_form_saves_with_the_request_tenant_and_a_cnx_number(
            self, tenant_a):
        """``TenantUniqueMixin`` stamps the tenant BEFORE validation, so the row saves straight from
        the form and ``TenantNumbered.save()`` mints the number — nobody types either."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(data=_integration_endpoint_post(), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("CNX-")
        assert len(obj.number) == len("CNX-00001")

    def test_integration_endpoint_numbers_restart_per_tenant(self, tenant_a, tenant_b):
        """Per-tenant numbering: workspace B's first connection is ``CNX-00001`` even though A
        already has one. A global sequence would leak A's volume to B."""
        from apps.scm.forms import IntegrationEndpointForm
        first = IntegrationEndpointForm(data=_integration_endpoint_post(), tenant=tenant_a)
        assert first.is_valid(), first.errors
        assert first.save().number == "CNX-00001"

        second = IntegrationEndpointForm(data=_integration_endpoint_post(), tenant=tenant_b)
        assert second.is_valid(), second.errors
        assert second.save().number == "CNX-00001"

    def test_integration_endpoint_form_leaves_every_system_column_at_its_default(self, tenant_a):
        """A saved row's derived counter and three system timestamps are untouched by the form,
        because the form cannot reach them at all."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(data=_integration_endpoint_post(), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.consecutive_failures == 0
        assert obj.last_run_at is None
        assert obj.last_success_at is None
        assert obj.last_seen_at is None
        assert obj.credential_prefix == ""
        assert obj.credential_hash == ""
        assert obj.masked == ""

    def test_integration_endpoint_edit_cannot_clear_a_registered_credential(
            self, tenant_a, integration_endpoint_with_credential_a):
        """The edit path is where L20 bites twice: the secret is neither RENDERED (it is not a field)
        nor OVERWRITTEN (a POST cannot name it). Round-tripping the whole form must leave both
        columns byte-identical."""
        from apps.scm.forms import IntegrationEndpointForm
        from apps.scm.models import IntegrationEndpoint
        before_prefix = integration_endpoint_with_credential_a.credential_prefix
        before_hash = integration_endpoint_with_credential_a.credential_hash
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(
                name=integration_endpoint_with_credential_a.name,
                credential_prefix="attacker", credential_hash="0" * 64),
            tenant=tenant_a, instance=integration_endpoint_with_credential_a)
        assert form.is_valid(), form.errors
        form.save()
        obj = IntegrationEndpoint.objects.get(pk=integration_endpoint_with_credential_a.pk)
        assert obj.credential_prefix == before_prefix
        assert obj.credential_hash == before_hash
        assert obj.credential_hash == IntegrationEndpoint.hash_secret("cred-plaintext-0123456789")

    def test_integration_endpoint_edit_render_never_contains_the_stored_hash(
            self, tenant_a, integration_endpoint_with_credential_a):
        """L20 asserted against the HTML the FORM generates, which is where the leak would be —
        masking in the template would not have helped."""
        from apps.scm.forms import IntegrationEndpointForm
        html = IntegrationEndpointForm(
            tenant=tenant_a, instance=integration_endpoint_with_credential_a).as_p()
        assert integration_endpoint_with_credential_a.credential_hash not in html
        assert "cred-plaintext-0123456789" not in html


# =================================================================================================
# IntegrationEndpointForm — the duplicate name (TenantUniqueMixin)
# =================================================================================================
class TestIntegrationEndpointFormUniqueness:
    def test_integration_endpoint_duplicate_name_in_the_same_tenant_is_a_form_error(
            self, tenant_a, integration_endpoint_a):
        """Without ``TenantUniqueMixin`` this passes ``is_valid()`` and then raises an uncaught
        ``IntegrityError`` on ``save()`` — a 500 on a mainline CRUD path, from an everyday mistake
        (registering "Shopify" twice). Django skips a ``unique_together`` ENTIRELY when any member
        field is excluded from validation, and ``tenant`` is never a form field."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(name=integration_endpoint_a.name), tenant=tenant_a)
        assert not form.is_valid()
        assert "already exists" in _integration_errors_text(form)

    def test_integration_endpoint_same_name_in_another_tenant_is_allowed(
            self, tenant_b, integration_endpoint_a):
        """The constraint is ``("tenant", "name")``, never a bare global ``unique=True`` — one
        workspace's naming must not block another's."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(name=integration_endpoint_a.name), tenant=tenant_b)
        assert form.is_valid(), form.errors
        assert form.save().tenant_id == tenant_b.pk

    def test_integration_endpoint_editing_a_row_without_renaming_it_is_allowed(
            self, tenant_a, integration_endpoint_a):
        """The uniqueness check must exclude the instance being edited, or every edit that keeps the
        name would refuse itself."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(name=integration_endpoint_a.name,
                                            notes="Re-pointed at the new OData path."),
            tenant=tenant_a, instance=integration_endpoint_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.number == integration_endpoint_a.number


# =================================================================================================
# IntegrationEndpointForm — CONSTRAINT A (a 3PL client already owns the interchange identity)
# =================================================================================================
class TestIntegrationEndpointFormConstraintA:
    def test_integration_endpoint_interchange_id_is_refused_when_a_client_is_named(
            self, tenant_a, tpl_client_shared_a):
        """4.17's ``LogisticsClient`` already holds this partner's ``edi_partner_id``. A second copy
        here is a second thing to keep true, and the stale one is always the copy an envelope gets
        built from — so it is REFUSED rather than silently ignored (a value the user typed and the
        system quietly drops is worse than an error, because they leave believing it applied)."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(logistics_client=tpl_client_shared_a.pk,
                                            interchange_id="ZZ99999999"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "interchange_id" in form.errors
        assert "3pl client" in _integration_errors_text(form)
        assert "shared" in _integration_errors_text(form)  # the client's code, named in the message

    def test_integration_endpoint_interchange_qualifier_is_refused_when_a_client_is_named(
            self, tenant_a, tpl_client_shared_a):
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(logistics_client=tpl_client_shared_a.pk,
                                            interchange_qualifier="ZZ"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "interchange_qualifier" in form.errors

    def test_integration_endpoint_both_interchange_fields_are_refused_together(
            self, tenant_a, tpl_client_shared_a):
        """Both keys are on the form, which is what makes the refusal RENDERABLE — a model error
        keyed on a column the form lacks raises ``ValueError`` out of ``add_error`` (a 500)."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(logistics_client=tpl_client_shared_a.pk,
                                            interchange_id="ZZ99999999",
                                            interchange_qualifier="ZZ"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert {"interchange_id", "interchange_qualifier"} <= set(form.errors)

    def test_integration_endpoint_a_named_client_with_a_blank_pair_is_accepted(
            self, tenant_a, tpl_client_shared_a):
        """The legal shape: link the client, leave both blank, and the connection READS the
        identity through the FK."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(logistics_client=tpl_client_shared_a.pk),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.interchange_id == ""
        assert obj.effective_interchange_id == "1234567890123"
        assert obj.effective_interchange_qualifier == "ZZ"

    def test_integration_endpoint_own_interchange_pair_is_accepted_without_a_client(self, tenant_a):
        """The other legal shape: no 3PL client, so the row carries its OWN pair and
        ``effective_interchange_id`` reads straight off the column."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(interchange_id="ZZ12345678",
                                            interchange_qualifier="ZZ"),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.effective_interchange_id == "ZZ12345678"
        assert obj.effective_interchange_qualifier == "ZZ"

    def test_integration_endpoint_whitespace_only_interchange_id_is_not_a_violation(
            self, tenant_a, tpl_client_shared_a):
        """The guard tests ``.strip()``, so a field containing only spaces is "blank" — refusing it
        would be refusing an empty field."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(logistics_client=tpl_client_shared_a.pk,
                                            interchange_id="   "),
            tenant=tenant_a)
        assert form.is_valid(), form.errors


# =================================================================================================
# IntegrationEndpointForm — tenant-scoped dropdowns and the crafted POST
# =================================================================================================
class TestIntegrationEndpointFormTenantScoping:
    def test_integration_endpoint_form_has_exactly_the_four_documented_dropdowns(
            self, _integration_endpoint_form):
        """The same four names as ``IntegrationEndpoint.TENANT_SCOPED_FKS`` — one table read by both
        boundaries, so a fifth FK added to the model without being added to that tuple shows up as a
        mismatch here rather than as an unguarded pointer in production."""
        from apps.scm.models import IntegrationEndpoint
        assert set(_integration_model_choice_fields(_integration_endpoint_form)) == \
            set(_integration_ENDPOINT_FKS)
        assert IntegrationEndpoint.TENANT_SCOPED_FKS == _integration_ENDPOINT_FKS

    @pytest.mark.parametrize("field", _integration_ENDPOINT_FKS)
    def test_integration_endpoint_dropdown_offers_this_tenants_rows(
            self, tenant_a, field, supplier_a, tpl_client_shared_a, location_a,
            evidence_document_a):
        """Positive half of the isolation assertion — scoping must not empty the select."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(tenant=tenant_a)
        assert form.fields[field].queryset.exists()

    @pytest.mark.parametrize("field,fixture_name", [
        ("partner_party", "supplier_b"),
        ("logistics_client", "tpl_client_b"),
        ("location", "location_b"),
        ("spec_document", "evidence_document_b"),
    ])
    def test_integration_endpoint_dropdown_excludes_another_workspaces_row(
            self, request, tenant_a, field, fixture_name):
        foreign = request.getfixturevalue(fixture_name)
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(tenant=tenant_a)
        assert foreign.pk not in set(form.fields[field].queryset.values_list("pk", flat=True))

    @pytest.mark.parametrize("field,fixture_name", [
        ("partner_party", "supplier_b"),
        ("logistics_client", "tpl_client_b"),
        ("location", "location_b"),
        ("spec_document", "evidence_document_b"),
    ])
    def test_integration_endpoint_crafted_post_with_a_foreign_pk_is_refused(
            self, request, tenant_a, field, fixture_name):
        """The mandatory crafted-POST case: a tenant B pk typed into an FK field never saves."""
        foreign = request.getfixturevalue(fixture_name)
        from apps.scm.forms import IntegrationEndpointForm
        from apps.scm.models import IntegrationEndpoint
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(**{field: foreign.pk}), tenant=tenant_a)
        assert not form.is_valid()
        assert field in form.errors
        assert not IntegrationEndpoint.objects.filter(name="Partner AS2 interchange").exists()

    @pytest.mark.parametrize("field,fixture_name", [
        ("partner_party", "supplier_b"),
        ("logistics_client", "tpl_client_b"),
        ("location", "location_b"),
        ("spec_document", "evidence_document_b"),
    ])
    def test_integration_endpoint_reject_foreign_holds_when_the_dropdown_is_widened(
            self, request, tenant_a, field, fixture_name):
        """The SECOND boundary, made observable.

        With the ``<select>`` widened out from under the form (the regression ``_reject_foreign``
        exists for) the field-level "not one of the available choices" check no longer fires — and
        the row must STILL be refused, with the message that names the reason.
        """
        foreign = request.getfixturevalue(fixture_name)
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(
            data=_integration_endpoint_post(**{field: foreign.pk}), tenant=tenant_a)
        _integration_widen_fk(form, field)
        assert not form.is_valid()
        assert field in form.errors
        assert "another workspace" in _integration_errors_text(form)

    def test_integration_endpoint_edit_still_offers_its_stored_pointer(
            self, tenant_a, integration_endpoint_client_a):
        """``_keep_current`` unions the CURRENTLY-STORED choice back into the dropdown, so opening
        the page to fix a typo cannot silently NULL a field nobody touched. A no-op while nothing
        narrows past tenant scoping — it is there so a narrowing added later inherits the
        protection instead of quietly regressing."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(tenant=tenant_a, instance=integration_endpoint_client_a)
        offered = set(form.fields["logistics_client"].queryset.values_list("pk", flat=True))
        assert integration_endpoint_client_a.logistics_client_id in offered

    def test_integration_endpoint_logistics_client_dropdown_joins_its_party(
            self, tenant_a, tpl_client_a, tpl_client_shared_a, django_assert_max_num_queries):
        """``LogisticsClient.__str__`` is ``f"{code} · {party}"``, so without ``select_related`` this
        ``<select>`` costs one query PER OPTION on both the create and the edit page — the chained
        ``__str__`` FK hop that N+1 guards exist to catch."""
        from apps.scm.forms import IntegrationEndpointForm
        form = IntegrationEndpointForm(tenant=tenant_a)
        assert form.fields["logistics_client"].queryset.query.select_related
        with django_assert_max_num_queries(2):
            str(form["logistics_client"])


# =================================================================================================
# WebhookSubscriptionForm — shape
# =================================================================================================
class TestIntegrationWebhookSubscriptionFormShape:
    def test_integration_subscription_form_field_order_is_pinned(
            self, _integration_subscription_form):
        assert list(_integration_subscription_form.fields) == \
            _integration_EXPECTED_FIELDS["WebhookSubscriptionForm"]

    def test_integration_subscription_form_required_fields(self, _integration_subscription_form):
        """``name`` / ``trigger_entity`` / ``target_url`` have no default; ``trigger_event``,
        ``payload_format`` and ``auto_disable_threshold`` DO have model defaults but are still
        required INPUTS on a bound form (Django renders them with an initial, so a browser always
        posts them)."""
        required = {name for name, field in _integration_subscription_form.fields.items()
                    if field.required}
        assert required == {"name", "trigger_entity", "target_url", "trigger_event",
                            "payload_format", "auto_disable_threshold"}

    def test_integration_subscription_form_has_no_foreign_key_dropdown_at_all(
            self, _integration_subscription_form):
        """Stated so the ABSENCE reads as a decision rather than an omission: this model points at
        no party, no partner and no document, so ``TENANT_SCOPED_FKS`` is ``()`` and there is
        deliberately no ``clean()`` / ``_reject_foreign`` on the class. Nothing is missing — there
        is nothing to scope."""
        from apps.scm.models import WebhookSubscription
        assert _integration_model_choice_fields(_integration_subscription_form) == {}
        assert WebhookSubscription.TENANT_SCOPED_FKS == ()
        fks = [f.name for f in WebhookSubscription._meta.fields
               if f.is_relation and f.name != "tenant"]
        assert fks == []

    def test_integration_subscription_form_widget_overrides_are_present(
            self, _integration_subscription_form):
        fields = _integration_subscription_form.fields
        assert isinstance(fields["headers"].widget, django_forms.Textarea)
        assert fields["headers"].widget.attrs.get("rows") == 3
        assert isinstance(fields["description"].widget, django_forms.Textarea)
        assert fields["description"].widget.attrs.get("rows") == 3

    def test_integration_subscription_form_help_texts_say_nothing_delivers_yet(
            self, _integration_subscription_form):
        """The two "recorded, never evaluated" fields read as working features without a note that
        says otherwise, which is the whole reason ``__init__`` overrides these three."""
        fields = _integration_subscription_form.fields
        assert "not yet switched on" in fields["target_url"].help_text.lower()
        assert "json object" in fields["headers"].help_text.lower()
        assert "1-20" in fields["auto_disable_threshold"].help_text


# =================================================================================================
# WebhookSubscriptionForm — validation
# =================================================================================================
class TestIntegrationWebhookSubscriptionFormValidation:
    def test_integration_subscription_form_accepts_a_valid_body(self, tenant_a):
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(data=_integration_subscription_post(), tenant=tenant_a)
        assert form.is_valid(), form.errors

    @pytest.mark.parametrize("field", ["name", "trigger_entity", "target_url"])
    def test_integration_subscription_form_rejects_a_missing_required_field(self, tenant_a, field):
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(**{field: ""}), tenant=tenant_a)
        assert not form.is_valid()
        assert field in form.errors
        assert "required" in _integration_errors_text(form)

    def test_integration_subscription_form_rejects_an_empty_body_entirely(self, tenant_a):
        """Every required field is named at once, so the page comes back with all the news rather
        than one error at a time."""
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(data={}, tenant=tenant_a)
        assert not form.is_valid()
        assert {"name", "trigger_entity", "target_url", "trigger_event", "payload_format",
                "auto_disable_threshold"} <= set(form.errors)

    @pytest.mark.parametrize("field,value", [
        ("trigger_entity", "invoice"),
        ("trigger_event", "exploded"),
        ("payload_format", "yaml"),
    ])
    def test_integration_subscription_form_rejects_a_value_outside_its_choices(
            self, tenant_a, field, value):
        """``trigger_entity``'s vocabulary is the list of VERIFIED existing scm classes — a value
        outside it names a record type nothing could ever publish."""
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(**{field: value}), tenant=tenant_a)
        assert not form.is_valid()
        assert field in form.errors

    @pytest.mark.parametrize("url", [
        "not-a-url",
        "sftp://sftp.partner.example.com/hook",
        "javascript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "",
    ])
    def test_integration_subscription_target_url_rejects_a_non_http_value(self, tenant_a, url):
        """The DELIBERATE asymmetry with ``IntegrationEndpoint.endpoint_url``: a webhook target
        really is HTTP(S), so ``URLField``'s http/https/ftp/ftps restriction excludes nothing
        legitimate here — and it excludes ``javascript:`` , which would otherwise be stored and one
        day rendered as a link."""
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(target_url=url), tenant=tenant_a)
        assert not form.is_valid()
        assert "target_url" in form.errors

    def test_integration_subscription_target_url_normalises_a_scheme_less_value(self, tenant_a):
        """A scheme-less target is NOT refused — Django's ``URLField`` supplies one
        (``assume_scheme``), so ``//example.com/hook`` is stored absolute rather than as the
        protocol-relative string a sender could not use.

        NOTE for a future transport pass: the project does not set ``FORMS_URLFIELD_ASSUME_HTTPS``,
        so the scheme supplied on Django 5.1 is ``http`` — this field's own help text says HTTPS. The
        assertion is deliberately scheme-agnostic so it survives the Django 6.0 default flip; what it
        pins is that the stored value is always absolute.
        """
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(target_url="//example.com/hook"), tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["target_url"].startswith(("http://", "https://"))
        assert form.cleaned_data["target_url"].endswith("//example.com/hook")

    def test_integration_subscription_target_url_is_length_bounded(self, tenant_a):
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(
                target_url="https://example.com/" + "p" * 500),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "target_url" in form.errors

    @pytest.mark.parametrize("value", ["0", "21", "-1", "abc", "NaN", "Infinity", "9" * 21])
    def test_integration_subscription_threshold_rejects_an_out_of_range_or_junk_value(
            self, tenant_a, value):
        """A retry budget is bounded 1..20, and the junk cases matter as much as the range ones: a
        hand-parsed number is where ``NaN`` / ``Infinity`` / a 21-digit integer turn a form error
        into a 500."""
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(auto_disable_threshold=value), tenant=tenant_a)
        assert not form.is_valid()
        assert "auto_disable_threshold" in form.errors

    @pytest.mark.parametrize("value", ["1", "8", "20"])
    def test_integration_subscription_threshold_accepts_its_boundaries(self, tenant_a, value):
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(auto_disable_threshold=value,
                                                name=f"Rule with a budget of {value}"),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["auto_disable_threshold"] == int(value)

    def test_integration_subscription_form_saves_with_the_request_tenant_and_a_whk_number(
            self, tenant_a):
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(data=_integration_subscription_post(), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.number == "WHK-00001"
        assert obj.consecutive_failures == 0
        assert obj.last_delivery_at is None
        assert obj.signing_secret_prefix == ""
        assert obj.signing_secret_hash == ""
        assert obj.masked == ""

    def test_integration_subscription_edit_cannot_clear_a_registered_signing_secret(
            self, tenant_a, integration_subscription_with_secret_a):
        """L20 on the other secret pair: a POST naming the two columns changes neither, because the
        form has no field to bind them to."""
        from apps.scm.forms import WebhookSubscriptionForm
        from apps.scm.models import WebhookSubscription
        before = integration_subscription_with_secret_a.signing_secret_hash
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(
                name=integration_subscription_with_secret_a.name,
                target_url=integration_subscription_with_secret_a.target_url,
                trigger_entity="goods_receipt", trigger_event="posted", payload_format="xml",
                signing_secret_prefix="attacker", signing_secret_hash="0" * 64),
            tenant=tenant_a, instance=integration_subscription_with_secret_a)
        assert form.is_valid(), form.errors
        form.save()
        obj = WebhookSubscription.objects.get(pk=integration_subscription_with_secret_a.pk)
        assert obj.signing_secret_hash == before
        assert obj.signing_secret_prefix == "whk-plai"

    def test_integration_subscription_edit_render_never_contains_the_stored_hash(
            self, tenant_a, integration_subscription_with_secret_a):
        from apps.scm.forms import WebhookSubscriptionForm
        html = WebhookSubscriptionForm(
            tenant=tenant_a, instance=integration_subscription_with_secret_a).as_p()
        assert integration_subscription_with_secret_a.signing_secret_hash not in html
        assert "whk-plaintext-0123456789" not in html

    def test_integration_subscription_duplicate_name_in_the_same_tenant_is_refused(
            self, tenant_a, integration_subscription_a):
        """Re-using a name is the ordinary mistake on this page (somebody adds a second rule rather
        than editing the first). ``TenantUniqueMixin`` turns it from an uncaught ``IntegrityError``
        into a message on the page."""
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(name=integration_subscription_a.name),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "already exists" in _integration_errors_text(form)

    def test_integration_subscription_same_name_in_another_tenant_is_allowed(
            self, tenant_b, integration_subscription_a):
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(name=integration_subscription_a.name),
            tenant=tenant_b)
        assert form.is_valid(), form.errors
        assert form.save().tenant_id == tenant_b.pk


# =================================================================================================
# WebhookSubscriptionForm.clean_headers — the three refusals
# =================================================================================================
class TestIntegrationWebhookHeadersValidation:
    @pytest.mark.parametrize("raw,expected", [
        ('{"X-Source": "NavERP"}', {"X-Source": "NavERP"}),
        ('{}', {}),
        ('', {}),
        ('{"X-Source": "NavERP", "X-Tenant": "acme"}', {"X-Source": "NavERP", "X-Tenant": "acme"}),
        # JSON `null` deserialises to Python None, which `clean_headers` folds into {} by its very
        # first line — the same answer as an empty box, and the reason the column can stay NOT NULL.
        ('null', {}),
    ])
    def test_integration_headers_accepts_a_flat_string_object(self, tenant_a, raw, expected):
        """A blank body becomes ``{}`` rather than ``None`` — the model column is ``default=dict``
        and a NULL there would be a second spelling of "no headers"."""
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(headers=raw), tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["headers"] == expected

    @pytest.mark.parametrize("raw", ['["a", "b"]', '"just a string"', '42', 'true', 'false',
                                     '[{"X-Source": "NavERP"}]'])
    def test_integration_headers_rejects_a_non_object(self, tenant_a, raw):
        """A list / string / number would crash the future sender the moment it called ``.items()``
        — a config error surfacing as a 500 in a background job rather than as a field error on the
        page where it was typed."""
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(headers=raw), tenant=tenant_a)
        assert not form.is_valid()
        assert "headers" in form.errors

    def test_integration_headers_rejects_invalid_json_outright(self, tenant_a):
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(headers="{not json at all"), tenant=tenant_a)
        assert not form.is_valid()
        assert "headers" in form.errors

    @pytest.mark.parametrize("raw", ['{"X-Retries": 3}', '{"X-Flag": true}', '{"X-Nested": {}}',
                                     '{"X-List": ["a"]}', '{"X-Null": null}'])
    def test_integration_headers_rejects_a_non_string_value(self, tenant_a, raw):
        """Non-strings serialise unpredictably into an HTTP header line."""
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(headers=raw), tenant=tenant_a)
        assert not form.is_valid()
        assert "headers" in form.errors
        assert "must be strings" in _integration_errors_text(form)

    @pytest.mark.parametrize("raw", [
        '{"X-Source": "NavERP\\r\\nX-Forwarded-For: 10.0.0.1"}',
        '{"X-Source": "NavERP\\nX-Injected: 1"}',
        '{"X-Bad\\r\\nX-Injected": "value"}',
        '{"X-Bad\\nkey": "value"}',
    ])
    def test_integration_headers_rejects_a_newline_in_either_half(self, tenant_a, raw):
        """A CR or LF in a header is REQUEST SPLITTING, not formatting: a value ending
        ``\\r\\nX-Forwarded-For: …`` appends an attacker-chosen header, and a full ``\\r\\n\\r\\n``
        an attacker-chosen BODY. Validated at the point of ENTRY because this column is written
        today and read by a transport pass that does not exist yet."""
        from apps.scm.forms import WebhookSubscriptionForm
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(headers=raw), tenant=tenant_a)
        assert not form.is_valid()
        assert "headers" in form.errors
        assert "request splitting" in _integration_errors_text(form)

    def test_integration_headers_survives_a_round_trip_through_save(self, tenant_a):
        from apps.scm.forms import WebhookSubscriptionForm
        from apps.scm.models import WebhookSubscription
        form = WebhookSubscriptionForm(
            data=_integration_subscription_post(headers='{"X-Source": "NavERP"}'), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert WebhookSubscription.objects.get(pk=obj.pk).headers == {"X-Source": "NavERP"}


# =================================================================================================
# The two APPEND-ONLY logs have no form at all — asserted positively
# =================================================================================================
class TestIntegrationAppendOnlyLogsHaveNoForm:
    @pytest.mark.parametrize("name", ["IntegrationMessageForm", "WebhookDeliveryForm"])
    def test_integration_no_form_class_exists_for_an_append_only_log(self, name):
        """``IntegrationMessage`` and ``WebhookDelivery`` are exchange EVIDENCE. A form would be an
        edit path onto a log, which is the one thing a log must not have."""
        from apps.scm import forms as scm_forms
        assert not hasattr(scm_forms, name)

    @pytest.mark.parametrize("module", ["IntegrationMessages", "WebhookDeliveries"])
    def test_integration_no_forms_module_exists_for_an_append_only_log(self, module):
        """The files are deliberately absent, not empty — asserted on disk AND through the import
        system, so a stub added later fails here."""
        path = (pathlib.Path(__file__).resolve().parents[1]
                / "forms" / "IntegrationApiGateway" / f"{module}.py")
        assert not path.exists(), f"{path} should not exist"
        assert importlib.util.find_spec(
            f"apps.scm.forms.IntegrationApiGateway.{module}") is None

    def test_integration_no_modelform_anywhere_in_scm_binds_an_append_only_log(self):
        """The strong version of the same rule: NOTHING in ``apps.scm.forms`` — under any name —
        may have ``Meta.model`` pointing at either log table."""
        from apps.scm import forms as scm_forms
        from apps.scm.models import IntegrationMessage, WebhookDelivery
        offenders = []
        for name in dir(scm_forms):
            candidate = getattr(scm_forms, name)
            if not isinstance(candidate, type) or not issubclass(
                    candidate, django_forms.BaseModelForm):
                continue
            model = getattr(getattr(candidate, "_meta", None), "model", None)
            if model in (IntegrationMessage, WebhookDelivery):
                offenders.append(name)
        assert not offenders, f"append-only logs bound to a ModelForm: {offenders}"

    @pytest.mark.parametrize("model_name,column", [
        ("IntegrationMessage", "number"),
        ("IntegrationMessage", "attempt_count"),
        ("IntegrationMessage", "occurred_at"),
        ("IntegrationMessage", "acknowledged_at"),
        ("WebhookDelivery", "triggered_at"),
    ])
    def test_integration_append_only_system_columns_stay_non_editable(self, model_name, column):
        """Even without a form, these columns must stay ``editable=False`` — that is what makes a
        later ``modelform_factory(..., fields="__all__")`` unable to open them."""
        from apps.scm import models as scm_models
        model = getattr(scm_models, model_name)
        assert model._meta.get_field(column).editable is False
