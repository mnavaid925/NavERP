"""SCM 4.19 Integration & API Gateway - MODEL invariants.

Four tables: ``IntegrationEndpoint`` [CNX-] (the connection register and the root of the
sub-module), ``IntegrationMessage`` [MSG-] (the append-only exchange log that CASCADEs off it),
``WebhookSubscription`` [WHK-] (the standing push rule) and ``WebhookDelivery`` (per-attempt
telemetry, deliberately UNNUMBERED).

What this lane pins, in the order the sub-module's own docstrings state it:

* **per-tenant auto-numbers** - CNX-/MSG-/WHK- mint, run in sequence inside a workspace and RESTART
  in the next one, because ``unique_together ("tenant", "number")`` is what lets two workspaces both
  legitimately hold a ``CNX-00001``. ``WebhookDelivery`` has no number at all, and its absence is a
  ruling rather than an oversight;
* **defaults and the closed vocabularies** - every value of all 17 CHOICES lists, plus the column
  widths that have to hold their longest member;
* **the two secret markers** - ``set_credential`` / ``set_signing_secret`` are the ONLY writers of
  their prefix+hash pairs, all four columns are ``editable=False`` (L20/L22 made structural rather
  than a promise a field list keeps), and the plaintext is never persisted anywhere;
* **everything DERIVED rather than stored** (L29) - ``masked``,
  ``effective_interchange_id``/``_qualifier`` (constraint A's read-through into 4.17's
  ``LogisticsClient``), ``next_backoff_seconds`` and ``MAX_ATTEMPTS`` are properties/derivations and
  not columns; the message and delivery roll-ups the pages render are ``.aggregate()`` calls over no
  stored counter;
* **the validation boundaries** - constraint A (an endpoint that names a 3PL client may not retype
  that client's interchange identity), the cross-tenant FK guard on all three models that have FKs,
  and the one self-reference that cannot mean anything (a message acknowledging itself);
* **the append-only shape** - ``external_id`` is deliberately NOT unique, ``IntegrationMessage``
  carries no GenericForeignKey (the app bans it), and its correlation is a soft pointer plus exactly
  two typed FKs.

Fixtures come from ``apps/scm/tests/conftest.py`` (the ``integration_`` block) and the ROOT
``conftest.py``. Nothing here writes to either file. Every moment is derived from
``timezone.now()`` - the same basis ``occurred_at`` / ``triggered_at`` read - never
``datetime.date.today()`` (L16). Nothing here reaches the network, and there is nothing to reach:
4.19 ships no transport at all.

NAMING: every test function is ``test_integration_*`` and every module-level helper or constant
``_integration_*``, so an adjacent sub-module appending nearby cannot shadow one of them (the guard
in ``test_suite_hygiene.py`` checks exactly that, per file).
"""
import datetime
import hashlib

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.scm.models import (
    AUTH_METHOD_CHOICES,
    DELIVERY_BACKOFF_SECONDS,
    DELIVERY_STATUS_CHOICES,
    DOCUMENT_TYPE_CHOICES,
    ENDPOINT_CATEGORY_CHOICES,
    ENDPOINT_DIRECTION_CHOICES,
    ENDPOINT_STATUS_CHOICES,
    ENDPOINT_SYSTEM_CHOICES,
    ENVIRONMENT_CHOICES,
    LIFECYCLE_STAGE_CHOICES,
    MESSAGE_DIRECTION_CHOICES,
    MESSAGE_SOURCE_CHOICES,
    MESSAGE_STATUS_CHOICES,
    PAYLOAD_FORMAT_CHOICES,
    TRANSPORT_CHOICES,
    TRIGGER_MODE_CHOICES,
    WEBHOOK_ENTITY_CHOICES,
    WEBHOOK_EVENT_CHOICES,
    IntegrationEndpoint,
    IntegrationMessage,
    TenantNumbered,
    TenantOwned,
    WebhookDelivery,
    WebhookSubscription,
)

pytestmark = pytest.mark.django_db


# =================================================================================================
# Helpers - every module-level name here is `_integration_`-prefixed so a neighbouring sub-module's
# file cannot shadow it (the suite-hygiene guard checks the same thing, per file).
# =================================================================================================

#: U+2014. Spelled as an escape rather than pasted so these assertions cannot be broken by an editor
#: helpfully "normalising" the character - all three ``__str__`` implementations use the EM DASH and
#: a hyphen would pass a careless eye.
_integration_EM_DASH = "—"

#: U+2022, the character both ``masked`` properties repeat eight times.
_integration_BULLET = "•"

#: The four 4.19 tables, in dependency order.
_integration_MODELS = (IntegrationEndpoint, IntegrationMessage, WebhookSubscription,
                       WebhookDelivery)


def _integration_values(choices):
    """Just the stored values of a CHOICES list - labels are prose and may be reworded."""
    return [value for value, _label in choices]


def _integration_field(model, name):
    return model._meta.get_field(name)


def _integration_field_names(model):
    return {field.name for field in model._meta.get_fields()}


def _integration_index_names(model):
    return {index.name for index in model._meta.indexes}


def _integration_clean_errors(instance):
    """``instance.clean()`` refused it - return the ``{field: [message, ...]}`` it refused with."""
    with pytest.raises(ValidationError) as excinfo:
        instance.clean()
    return excinfo.value.message_dict


def _integration_full_clean_errors(instance):
    """``full_clean`` errors, with ``number`` excluded.

    ``number`` is ``editable=False`` AND ``blank=False``, and ``Model.clean_fields`` does not skip
    non-editable columns - so an UNSAVED numbered instance always reports a blank ``number`` on top
    of whatever is actually under test. Excluding it keeps each assertion about its own field; the
    minting of the number itself is pinned separately.
    """
    with pytest.raises(ValidationError) as excinfo:
        instance.full_clean(exclude={"number"})
    return excinfo.value.message_dict


def _integration_endpoint(tenant, name, **kwargs):
    return IntegrationEndpoint.objects.create(tenant=tenant, name=name, **kwargs)


def _integration_message(tenant, endpoint, **kwargs):
    kwargs.setdefault("direction", "inbound")
    return IntegrationMessage.objects.create(tenant=tenant, endpoint=endpoint, **kwargs)


def _integration_subscription(tenant, name, **kwargs):
    kwargs.setdefault("trigger_entity", "shipment")
    kwargs.setdefault("target_url", "https://example.com/hook")
    return WebhookSubscription.objects.create(tenant=tenant, name=name, **kwargs)


def _integration_delivery(tenant, subscription, **kwargs):
    kwargs.setdefault("event", "shipment.delivered")
    return WebhookDelivery.objects.create(tenant=tenant, subscription=subscription, **kwargs)


def _integration_stored_text(instance):
    """Every text value actually persisted on ``instance`` - the haystack for a plaintext hunt."""
    instance.refresh_from_db()
    return [
        str(getattr(instance, field.attname))
        for field in instance._meta.fields
        if isinstance(field, (models.CharField, models.TextField))
    ]


# =================================================================================================
# 4.19 - the package surface: everything reaches callers through the package root
# =================================================================================================
def test_integration_the_four_models_import_through_the_package_root():
    """``apps/scm/models/__init__.py``'s re-export block is what lets the admin, the seeder, the
    views and these tests all reach one class. A model added to the sub-package WITHOUT being
    re-exported is an ImportError waiting for its first caller."""
    assert [model.__name__ for model in _integration_MODELS] == [
        "IntegrationEndpoint", "IntegrationMessage", "WebhookSubscription", "WebhookDelivery"]
    for model in _integration_MODELS:
        assert model._meta.app_label == "scm"


@pytest.mark.parametrize("vocabulary", [
    ENDPOINT_CATEGORY_CHOICES, ENDPOINT_SYSTEM_CHOICES, ENDPOINT_DIRECTION_CHOICES,
    TRANSPORT_CHOICES, AUTH_METHOD_CHOICES, TRIGGER_MODE_CHOICES, ENVIRONMENT_CHOICES,
    LIFECYCLE_STAGE_CHOICES, ENDPOINT_STATUS_CHOICES, MESSAGE_DIRECTION_CHOICES,
    DOCUMENT_TYPE_CHOICES, MESSAGE_STATUS_CHOICES, MESSAGE_SOURCE_CHOICES,
    WEBHOOK_ENTITY_CHOICES, WEBHOOK_EVENT_CHOICES, PAYLOAD_FORMAT_CHOICES,
    DELIVERY_STATUS_CHOICES,
])
def test_integration_every_vocabulary_is_a_deduplicated_pair_list(vocabulary):
    values = _integration_values(vocabulary)
    assert values, "an empty vocabulary renders an empty <select>"
    assert len(values) == len(set(values)), f"duplicate value in {values}"
    assert all(isinstance(value, str) and value == value.strip() for value in values)


def test_integration_all_eighteen_shared_names_are_re_exported():
    import apps.scm.models as package
    for name in (
        "ENDPOINT_CATEGORY_CHOICES", "ENDPOINT_SYSTEM_CHOICES", "ENDPOINT_DIRECTION_CHOICES",
        "TRANSPORT_CHOICES", "AUTH_METHOD_CHOICES", "TRIGGER_MODE_CHOICES", "ENVIRONMENT_CHOICES",
        "LIFECYCLE_STAGE_CHOICES", "ENDPOINT_STATUS_CHOICES", "MESSAGE_DIRECTION_CHOICES",
        "DOCUMENT_TYPE_CHOICES", "MESSAGE_STATUS_CHOICES", "MESSAGE_SOURCE_CHOICES",
        "WEBHOOK_ENTITY_CHOICES", "WEBHOOK_EVENT_CHOICES", "PAYLOAD_FORMAT_CHOICES",
        "DELIVERY_STATUS_CHOICES", "DELIVERY_BACKOFF_SECONDS",
    ):
        assert hasattr(package, name), f"{name} is not re-exported from apps.scm.models"


# =================================================================================================
# 4.19 - multi-tenancy: every table is tenant-scoped and no constraint is global
# =================================================================================================
@pytest.mark.parametrize("model", _integration_MODELS)
def test_integration_every_table_carries_a_cascading_tenant_fk(model):
    tenant_field = _integration_field(model, "tenant")
    assert tenant_field.remote_field.model._meta.label == "core.Tenant"
    assert tenant_field.remote_field.on_delete is models.CASCADE
    assert tenant_field.null is False


@pytest.mark.parametrize("model", _integration_MODELS)
def test_integration_no_column_is_globally_unique(model):
    """A bare ``unique=True`` would let one workspace's value block another's - every constraint in
    this sub-module starts with the tenant instead."""
    offenders = [f.name for f in model._meta.fields if f.unique and not f.primary_key]
    assert offenders == [], f"{model.__name__} has globally-unique columns: {offenders}"


@pytest.mark.parametrize("model", _integration_MODELS)
def test_integration_every_unique_together_pair_leads_with_the_tenant(model):
    for pair in model._meta.unique_together:
        assert pair[0] == "tenant", f"{model.__name__} constrains {pair} without leading on tenant"


@pytest.mark.parametrize("model", _integration_MODELS)
def test_integration_every_index_is_tenant_leading_and_scm_prefixed(model):
    """Index names are GLOBAL to the database, not scoped to the app - crm already owns
    ``crm_whd_tnt_*`` on its own ``WebhookDelivery``."""
    for index in model._meta.indexes:
        assert index.fields[0] == "tenant", f"{index.name} does not lead on tenant"
        assert index.name.startswith("scm_"), f"{index.name} is not scm-prefixed"


# =================================================================================================
# 4.19.1 IntegrationEndpoint [CNX-] - defaults
# =================================================================================================
@pytest.mark.parametrize("field, expected", [
    ("category", "custom"),
    ("system", ""),
    ("direction", "bidirectional"),
    ("transport", "api_rest"),
    ("auth_method", "none"),
    ("trigger_mode", "manual"),
    ("environment", "sandbox"),
    ("lifecycle_stage", "setup"),
    ("status", "disconnected"),
    ("is_active", True),
    ("consecutive_failures", 0),
    ("endpoint_url", ""),
    ("external_account_ref", ""),
    ("interchange_id", ""),
    ("interchange_qualifier", ""),
    ("device_identifier", ""),
    ("schedule_note", ""),
    ("notes", ""),
    ("credential_prefix", ""),
    ("credential_hash", ""),
])
def test_integration_endpoint_minimal_row_takes_its_documented_default(tenant_a, field, expected):
    """``IntegrationEndpoint.objects.create(tenant=..., name=...)`` is the MINIMAL valid row: every
    other column has a default or is blank."""
    endpoint = _integration_endpoint(tenant_a, "Minimal connection")
    assert getattr(endpoint, field) == expected


@pytest.mark.parametrize("field", [
    "partner_party", "logistics_client", "location", "spec_document",
    "last_run_at", "last_success_at", "last_seen_at",
])
def test_integration_endpoint_minimal_row_leaves_its_pointers_and_stamps_empty(tenant_a, field):
    endpoint = _integration_endpoint(tenant_a, "Minimal connection")
    assert getattr(endpoint, field) is None


def test_integration_endpoint_minimal_row_passes_full_clean(tenant_a):
    _integration_endpoint(tenant_a, "Minimal connection").full_clean()


def test_integration_endpoint_name_is_the_one_required_column(tenant_a):
    errors = _integration_full_clean_errors(IntegrationEndpoint(tenant=tenant_a))
    assert set(errors) == {"name"}


# =================================================================================================
# 4.19.1 IntegrationEndpoint - identity, numbering and __str__
# =================================================================================================
def test_integration_endpoint_str_is_number_em_dash_name(integration_endpoint_a):
    assert str(integration_endpoint_a) == (
        f"{integration_endpoint_a.number} {_integration_EM_DASH} {integration_endpoint_a.name}")


def test_integration_endpoint_declares_the_cnx_prefix_and_hides_the_column():
    """``editable=False`` is what keeps ``number`` off every ModelForm structurally, rather than
    through a field list somebody has to remember (L22)."""
    assert IntegrationEndpoint.NUMBER_PREFIX == "CNX"
    assert _integration_field(IntegrationEndpoint, "number").editable is False
    assert issubclass(IntegrationEndpoint, TenantNumbered)


def test_integration_endpoint_mints_a_five_digit_cnx_number(integration_endpoint_a):
    assert integration_endpoint_a.number == "CNX-00001"


def test_integration_endpoint_numbers_run_in_sequence_inside_one_workspace(tenant_a):
    first = _integration_endpoint(tenant_a, "First connection")
    second = _integration_endpoint(tenant_a, "Second connection")
    third = _integration_endpoint(tenant_a, "Third connection")
    assert [first.number, second.number, third.number] == [
        "CNX-00001", "CNX-00002", "CNX-00003"]


def test_integration_endpoint_number_sequence_restarts_in_each_workspace(
        integration_endpoint_a, integration_endpoint_b):
    """``unique_together ("tenant", "number")`` - the counter is per tenant, so both workspaces
    legitimately hold a ``CNX-00001`` and neither collides with the other."""
    assert integration_endpoint_a.number == integration_endpoint_b.number == "CNX-00001"
    assert integration_endpoint_a.tenant_id != integration_endpoint_b.tenant_id


def test_integration_endpoint_a_second_workspace_does_not_disturb_the_first(tenant_a, tenant_b):
    _integration_endpoint(tenant_b, "Globex one")
    _integration_endpoint(tenant_b, "Globex two")
    assert _integration_endpoint(tenant_a, "Acme one").number == "CNX-00001"


def test_integration_endpoint_duplicate_number_in_one_workspace_is_refused(
        tenant_a, integration_endpoint_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _integration_endpoint(tenant_a, "Another name",
                                  number=integration_endpoint_a.number)


def test_integration_endpoint_unique_together_names_both_pairs():
    assert IntegrationEndpoint._meta.unique_together == (
        ("tenant", "number"), ("tenant", "name"))


def test_integration_endpoint_duplicate_name_in_one_workspace_is_refused(
        tenant_a, integration_endpoint_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _integration_endpoint(tenant_a, integration_endpoint_a.name)


def test_integration_endpoint_two_workspaces_may_share_a_name(
        tenant_b, integration_endpoint_a):
    twin = _integration_endpoint(tenant_b, integration_endpoint_a.name)
    assert twin.name == integration_endpoint_a.name
    assert twin.tenant_id != integration_endpoint_a.tenant_id


def test_integration_endpoint_ordering_is_a_total_order():
    """``["name"]`` alone is not one: rows that tie are free to swap between page 1 and page 2 of
    the same paginated read, so a row can be shown twice or not at all (L9's sibling problem)."""
    assert IntegrationEndpoint._meta.ordering == ["name", "id"]


def test_integration_endpoint_declares_its_three_indexes():
    assert _integration_index_names(IntegrationEndpoint) == {
        "scm_cnx_tnt_cat_idx", "scm_cnx_tnt_status_idx", "scm_cnx_tnt_active_idx"}


# =================================================================================================
# 4.19.1 IntegrationEndpoint - the nine closed vocabularies
# =================================================================================================
def test_integration_endpoint_category_choices_are_the_four_sidebar_bullets_plus_custom():
    assert _integration_values(ENDPOINT_CATEGORY_CHOICES) == [
        "erp", "ecommerce", "iot", "edi", "custom"]


def test_integration_endpoint_system_choices_cover_the_fifteen_surveyed_platforms():
    assert _integration_values(ENDPOINT_SYSTEM_CHOICES) == [
        "sap", "oracle", "netsuite", "dynamics", "shopify", "magento", "woocommerce", "amazon",
        "ebay", "walmart", "rfid_reader", "barcode_scanner", "sensor_gateway", "edi_van", "custom"]


def test_integration_endpoint_direction_choices():
    assert _integration_values(ENDPOINT_DIRECTION_CHOICES) == [
        "inbound", "outbound", "bidirectional"]


def test_integration_endpoint_transport_choices_are_wider_than_http():
    """EDI runs over as2/van/sftp and an RFID reader speaks llrp - which is exactly why
    ``endpoint_url`` is a CharField rather than a URLField."""
    assert _integration_values(TRANSPORT_CHOICES) == [
        "api_rest", "api_soap", "webhook", "sftp", "ftps", "as2", "van", "file_drop", "mqtt",
        "llrp", "serial", "manual"]


def test_integration_endpoint_auth_method_choices():
    assert _integration_values(AUTH_METHOD_CHOICES) == [
        "none", "api_key", "basic", "oauth2", "mtls", "ssh_key"]


def test_integration_endpoint_trigger_mode_choices_record_intent_only():
    assert _integration_values(TRIGGER_MODE_CHOICES) == ["realtime", "scheduled", "manual"]


def test_integration_endpoint_environment_choices_are_exactly_two():
    """No third "staging" that behaves like neither - that is how a test order reaches a live
    marketplace."""
    assert _integration_values(ENVIRONMENT_CHOICES) == ["production", "sandbox"]


def test_integration_endpoint_lifecycle_stage_choices_include_certified():
    assert _integration_values(LIFECYCLE_STAGE_CHOICES) == [
        "setup", "testing", "certified", "live", "suspended"]


def test_integration_endpoint_status_choices():
    assert _integration_values(ENDPOINT_STATUS_CHOICES) == [
        "disconnected", "connected", "error", "disabled"]


def test_integration_endpoint_lifecycle_stage_is_not_status():
    """How far onboarding has got is a different question from whether the link is up now, so the
    two vocabularies must not have been collapsed into one."""
    assert set(_integration_values(LIFECYCLE_STAGE_CHOICES)).isdisjoint(
        _integration_values(ENDPOINT_STATUS_CHOICES))


@pytest.mark.parametrize("field, vocabulary", [
    ("category", ENDPOINT_CATEGORY_CHOICES),
    ("system", ENDPOINT_SYSTEM_CHOICES),
    ("direction", ENDPOINT_DIRECTION_CHOICES),
    ("transport", TRANSPORT_CHOICES),
    ("auth_method", AUTH_METHOD_CHOICES),
    ("trigger_mode", TRIGGER_MODE_CHOICES),
    ("environment", ENVIRONMENT_CHOICES),
    ("lifecycle_stage", LIFECYCLE_STAGE_CHOICES),
    ("status", ENDPOINT_STATUS_CHOICES),
])
def test_integration_endpoint_choice_columns_are_wide_enough(field, vocabulary):
    """A ``max_length`` under the longest member truncates silently on MySQL and 500s nowhere until
    a filter stops matching."""
    column = _integration_field(IntegrationEndpoint, field)
    assert column.choices == vocabulary
    assert column.max_length >= max(len(value) for value in _integration_values(vocabulary))


def test_integration_endpoint_full_clean_rejects_a_value_outside_the_vocabulary(tenant_a):
    endpoint = _integration_endpoint(tenant_a, "Bad category")
    endpoint.category = "not_a_category"
    assert "category" in _integration_full_clean_errors(endpoint)


# =================================================================================================
# 4.19.1 IntegrationEndpoint - endpoint_url is deliberately NOT a URLField
# =================================================================================================
def test_integration_endpoint_url_is_a_charfield_not_a_urlfield():
    """URLValidator accepts only http/https/ftp/ftps, so a URLField would reject the legitimate
    sftp:// as2:// mqtt:// llrp:// endpoints this table exists to hold - and would reject them only
    at ModelForm validation, so the seeder passes and the UI fails."""
    column = _integration_field(IntegrationEndpoint, "endpoint_url")
    assert isinstance(column, models.CharField)
    assert not isinstance(column, models.URLField)
    assert column.max_length == 500


@pytest.mark.parametrize("url", [
    "sftp://edi.partner.example.net/outbound",
    "as2://as2.van-partner.example.net/exchange",
    "mqtt://sensors.internal.example.com:1883/scm",
    "llrp://10.20.4.17:5084",
    "https://sap-erp.internal.example.com/odata/v4/scm",
])
def test_integration_endpoint_accepts_a_non_http_scheme(tenant_a, url):
    endpoint = _integration_endpoint(tenant_a, f"Endpoint for {url}", endpoint_url=url)
    endpoint.full_clean()
    endpoint.refresh_from_db()
    assert endpoint.endpoint_url == url


# =================================================================================================
# 4.19.1 IntegrationEndpoint - system-maintained state is structurally off every form
# =================================================================================================
@pytest.mark.parametrize("field", [
    "number", "consecutive_failures", "last_run_at", "last_success_at", "last_seen_at",
    "credential_prefix", "credential_hash",
])
def test_integration_endpoint_system_state_columns_are_editable_false(field):
    """L20/L22: a secret or a derived counter in ``Meta.fields`` ships its value in the edit render.
    ``editable=False`` makes "no form can carry this" structural - a ModelForm cannot resurrect it
    even by naming it."""
    assert _integration_field(IntegrationEndpoint, field).editable is False


def test_integration_endpoint_system_state_is_still_assignable_at_create(
        integration_endpoint_iot_a):
    """``editable=False`` keeps a column off forms without taking it away from the seeder or an
    importer - the two are independent, which is why these are not ``auto_now`` columns."""
    assert integration_endpoint_iot_a.consecutive_failures == 3
    assert integration_endpoint_iot_a.last_run_at is not None
    assert integration_endpoint_iot_a.last_success_at is not None
    assert integration_endpoint_iot_a.last_seen_at is not None
    assert integration_endpoint_iot_a.last_success_at < integration_endpoint_iot_a.last_run_at


def test_integration_endpoint_failure_counter_is_recorded_never_enforced(
        integration_endpoint_iot_a):
    """Nothing decrements it and nothing auto-disables on it, because nothing delivers - the row is
    still active despite three recorded failures."""
    assert integration_endpoint_iot_a.is_active is True
    assert integration_endpoint_iot_a.status == "error"


def test_integration_endpoint_names_its_four_tenant_scoped_fks():
    """One tuple, two readers - the form's ``_reject_foreign`` and the model's own ``clean()``. A
    fifth FK inherits the check by being added here rather than by somebody writing a branch."""
    assert IntegrationEndpoint.TENANT_SCOPED_FKS == (
        "partner_party", "logistics_client", "location", "spec_document")
    for name in IntegrationEndpoint.TENANT_SCOPED_FKS:
        assert _integration_field(IntegrationEndpoint, name).is_relation


@pytest.mark.parametrize("field", ["partner_party", "logistics_client", "location",
                                   "spec_document"])
def test_integration_endpoint_pointers_are_nullable_set_null(field):
    """A registration outliving the party, client, bin or spec it referenced is a stale pointer, not
    a reason to destroy the exchange history hanging off it."""
    column = _integration_field(IntegrationEndpoint, field)
    assert column.remote_field.on_delete is models.SET_NULL
    assert column.null is True and column.blank is True


# =================================================================================================
# 4.19.1 IntegrationEndpoint - the credential MARKER (prefix + one-way hash)
# =================================================================================================
def test_integration_endpoint_masked_is_blank_when_no_credential_is_registered(
        integration_endpoint_a):
    assert integration_endpoint_a.credential_hash == ""
    assert integration_endpoint_a.masked == ""


def test_integration_endpoint_masked_is_prefix_plus_eight_bullets(
        integration_endpoint_with_credential_a):
    assert integration_endpoint_with_credential_a.masked == (
        "cred-pla" + _integration_BULLET * 8)


def test_integration_endpoint_masked_is_derived_not_stored():
    assert "masked" not in _integration_field_names(IntegrationEndpoint)
    assert isinstance(IntegrationEndpoint.masked, property)


def test_integration_endpoint_set_credential_writes_prefix_and_hash(tenant_a):
    endpoint = IntegrationEndpoint(tenant=tenant_a, name="Credential writer")
    endpoint.set_credential("cred-plaintext-0123456789")
    endpoint.save()
    endpoint.refresh_from_db()
    assert endpoint.credential_prefix == "cred-pla"
    assert endpoint.credential_hash == IntegrationEndpoint.hash_secret(
        "cred-plaintext-0123456789")


def test_integration_endpoint_hash_secret_is_sha256(tenant_a):
    expected = hashlib.sha256(b"cred-plaintext-0123456789").hexdigest()
    assert IntegrationEndpoint.hash_secret("cred-plaintext-0123456789") == expected
    assert len(expected) == 64


def test_integration_endpoint_hash_secret_is_deterministic_and_input_sensitive():
    """Deterministic is what makes a rotation DETECTABLE; input-sensitive is what makes the marker
    mean anything at all."""
    assert (IntegrationEndpoint.hash_secret("same") ==
            IntegrationEndpoint.hash_secret("same"))
    assert (IntegrationEndpoint.hash_secret("same") !=
            IntegrationEndpoint.hash_secret("same "))


def test_integration_endpoint_generate_credential_is_from_the_csprng():
    """``secrets.token_urlsafe(24)`` - never ``random`` (seeded, predictable) and never
    ``uuid4().hex`` (an identifier whose entropy layout is public)."""
    minted = {IntegrationEndpoint.generate_credential() for _ in range(64)}
    assert len(minted) == 64
    assert all(len(value) >= 30 for value in minted)


def test_integration_endpoint_rotating_the_credential_changes_the_hash(tenant_a):
    endpoint = IntegrationEndpoint(tenant=tenant_a, name="Rotation")
    endpoint.set_credential("first-credential-value")
    endpoint.save()
    before = endpoint.credential_hash
    endpoint.set_credential("second-credential-value")
    endpoint.save()
    assert endpoint.credential_hash != before
    assert endpoint.credential_prefix == "second-c"


def test_integration_endpoint_plaintext_credential_is_never_persisted(
        integration_endpoint_with_credential_a):
    """The whole point of the marker: the row identifies WHICH credential is registered and holds
    none of a credential store's liability."""
    plaintext = "cred-plaintext-0123456789"
    stored = _integration_stored_text(integration_endpoint_with_credential_a)
    assert all(plaintext not in value for value in stored)
    assert plaintext not in str(integration_endpoint_with_credential_a.__dict__)


def test_integration_endpoint_credential_hash_is_not_reversible_to_the_prefix(
        integration_endpoint_with_credential_a):
    endpoint = integration_endpoint_with_credential_a
    assert endpoint.credential_hash != endpoint.credential_prefix
    assert len(endpoint.credential_hash) == 64
    assert endpoint.credential_prefix not in endpoint.credential_hash


# =================================================================================================
# 4.19.1 IntegrationEndpoint - constraint A, the 4.17 ownership boundary
# =================================================================================================
def test_integration_endpoint_effective_interchange_reads_its_own_columns_without_a_client(
        integration_endpoint_edi_a):
    assert integration_endpoint_edi_a.logistics_client_id is None
    assert integration_endpoint_edi_a.effective_interchange_id == "ZZ12345678"
    assert integration_endpoint_edi_a.effective_interchange_qualifier == "ZZ"


def test_integration_endpoint_effective_interchange_reads_through_the_logistics_client(
        integration_endpoint_client_a, tpl_client_shared_a):
    """One place a partner's ISA id lives. The endpoint's own pair stays blank and the value comes
    off 4.17's client record through the FK."""
    assert integration_endpoint_client_a.interchange_id == ""
    assert integration_endpoint_client_a.interchange_qualifier == ""
    assert integration_endpoint_client_a.effective_interchange_id == (
        tpl_client_shared_a.edi_partner_id)
    assert integration_endpoint_client_a.effective_interchange_qualifier == (
        tpl_client_shared_a.edi_qualifier)


def test_integration_endpoint_effective_interchange_follows_the_client_after_an_edit(
        integration_endpoint_client_a, tpl_client_shared_a):
    """A read-through, not a copy: editing the client record changes what the endpoint reports,
    which is precisely what a second stored column would fail to do."""
    tpl_client_shared_a.edi_partner_id = "9876543210987"
    tpl_client_shared_a.save(update_fields=["edi_partner_id"])
    integration_endpoint_client_a.refresh_from_db()
    assert integration_endpoint_client_a.effective_interchange_id == "9876543210987"


def test_integration_endpoint_effective_interchange_is_derived_not_stored():
    names = _integration_field_names(IntegrationEndpoint)
    assert "effective_interchange_id" not in names
    assert "effective_interchange_qualifier" not in names
    assert isinstance(IntegrationEndpoint.effective_interchange_id, property)
    assert isinstance(IntegrationEndpoint.effective_interchange_qualifier, property)


def test_integration_endpoint_adds_no_column_that_4_17_already_owns():
    """4.19 re-declares none of ``LogisticsClient``'s five integration columns - that is the whole
    of constraint A stated as a schema fact."""
    names = _integration_field_names(IntegrationEndpoint)
    assert names.isdisjoint({"integration_mode", "client_system", "edi_partner_id",
                             "edi_qualifier", "last_synced_at"})


def test_integration_endpoint_clean_refuses_an_own_interchange_id_beside_a_client(
        tenant_a, tpl_client_shared_a):
    endpoint = IntegrationEndpoint(tenant=tenant_a, name="Retyped id",
                                   logistics_client=tpl_client_shared_a,
                                   interchange_id="ZZ99999999")
    errors = _integration_clean_errors(endpoint)
    assert set(errors) == {"interchange_id"}
    assert "SHARED" in errors["interchange_id"][0]


def test_integration_endpoint_clean_refuses_an_own_qualifier_beside_a_client(
        tenant_a, tpl_client_shared_a):
    endpoint = IntegrationEndpoint(tenant=tenant_a, name="Retyped qualifier",
                                   logistics_client=tpl_client_shared_a,
                                   interchange_qualifier="01")
    assert set(_integration_clean_errors(endpoint)) == {"interchange_qualifier"}


def test_integration_endpoint_clean_reports_both_interchange_fields_at_once(
        tenant_a, tpl_client_shared_a):
    """Both, in one pass - a form that fixes one error only to be handed the second is a round trip
    the user did not need."""
    endpoint = IntegrationEndpoint(tenant=tenant_a, name="Retyped both",
                                   logistics_client=tpl_client_shared_a,
                                   interchange_id="ZZ99999999", interchange_qualifier="01")
    assert set(_integration_clean_errors(endpoint)) == {
        "interchange_id", "interchange_qualifier"}


def test_integration_endpoint_clean_treats_whitespace_as_blank(tenant_a, tpl_client_shared_a):
    endpoint = IntegrationEndpoint(tenant=tenant_a, name="Whitespace only",
                                   logistics_client=tpl_client_shared_a,
                                   interchange_id="   ", interchange_qualifier=" ")
    assert endpoint.clean() is None


def test_integration_endpoint_clean_accepts_a_linked_row_with_a_blank_pair(
        integration_endpoint_client_a):
    assert integration_endpoint_client_a.clean() is None


def test_integration_endpoint_clean_accepts_its_own_pair_without_a_client(
        integration_endpoint_edi_a):
    assert integration_endpoint_edi_a.clean() is None


def test_integration_endpoint_clean_error_keys_are_all_editable_columns():
    """A model error keyed on a column the form lacks raises ``ValueError`` out of ``add_error`` - a
    500 instead of a field error (L39)."""
    editable = {f.name for f in IntegrationEndpoint._meta.fields if f.editable}
    keys = {"interchange_id", "interchange_qualifier"} | set(
        IntegrationEndpoint.TENANT_SCOPED_FKS)
    assert keys <= editable


# =================================================================================================
# 4.19.1 IntegrationEndpoint - the cross-tenant pointer guard
# =================================================================================================
@pytest.mark.parametrize("field, fixture_name", [
    ("partner_party", "supplier_b"),
    ("logistics_client", "tpl_client_b"),
    ("location", "location_b"),
    ("spec_document", "evidence_document_b"),
])
def test_integration_endpoint_clean_rejects_a_cross_tenant_pointer(
        request, tenant_a, field, fixture_name):
    foreign = request.getfixturevalue(fixture_name)
    endpoint = IntegrationEndpoint(tenant=tenant_a, name=f"Foreign {field}",
                                   **{field: foreign})
    errors = _integration_clean_errors(endpoint)
    assert set(errors) == {field}
    assert errors[field] == ["That record belongs to another workspace."]


@pytest.mark.parametrize("field, fixture_name", [
    ("partner_party", "supplier_a"),
    ("logistics_client", "tpl_client_shared_a"),
    ("location", "location_a"),
    ("spec_document", "evidence_document_a"),
])
def test_integration_endpoint_clean_accepts_a_same_tenant_pointer(
        request, tenant_a, field, fixture_name):
    own = request.getfixturevalue(fixture_name)
    endpoint = IntegrationEndpoint(tenant=tenant_a, name=f"Own {field}", **{field: own})
    assert endpoint.clean() is None


def test_integration_endpoint_clean_is_skipped_while_the_row_has_no_tenant(location_b):
    """An unsaved row with no tenant cannot be compared against one - and reading ``self.tenant`` on
    a non-nullable FK would raise rather than return None."""
    assert IntegrationEndpoint(name="Tenantless", location=location_b).clean() is None


# =================================================================================================
# 4.19.2 IntegrationMessage [MSG-] - defaults and the required direction
# =================================================================================================
@pytest.mark.parametrize("field, expected", [
    ("document_type", "other"),
    ("status", "pending"),
    ("source", "none"),
    ("record_count", 0),
    ("attempt_count", 1),
    ("control_number", ""),
    ("external_id", ""),
    ("source_reference", ""),
    ("payload_excerpt", ""),
    ("error_code", ""),
    ("error_message", ""),
])
def test_integration_message_minimal_row_takes_its_documented_default(
        tenant_a, integration_endpoint_a, field, expected):
    message = _integration_message(tenant_a, integration_endpoint_a)
    assert getattr(message, field) == expected


@pytest.mark.parametrize("field", ["acknowledged_at", "acknowledges", "purchase_order",
                                   "sales_order"])
def test_integration_message_minimal_row_leaves_its_pointers_empty(
        tenant_a, integration_endpoint_a, field):
    message = _integration_message(tenant_a, integration_endpoint_a)
    assert getattr(message, field) is None


def test_integration_message_direction_has_no_default(tenant_a, integration_endpoint_a):
    """Which way a message travelled is never a safe assumption - a default here would file inbound
    partner traffic as something we sent."""
    assert _integration_field(IntegrationMessage, "direction").has_default() is False
    blank = IntegrationMessage(tenant=tenant_a, endpoint=integration_endpoint_a)
    assert "direction" in _integration_full_clean_errors(blank)


def test_integration_message_occurred_at_defaults_to_now_and_is_assignable(
        tenant_a, integration_endpoint_a):
    """``default=timezone.now`` rather than ``auto_now_add``: a message that crossed at 02:14 and
    was recorded at 02:31 must be filed at 02:14, so a back-dated import can say so."""
    assert _integration_field(IntegrationMessage, "occurred_at").default is timezone.now
    fresh = _integration_message(tenant_a, integration_endpoint_a)
    assert abs((timezone.now() - fresh.occurred_at).total_seconds()) < 60

    backdated_at = timezone.now() - datetime.timedelta(days=9)
    backdated = _integration_message(tenant_a, integration_endpoint_a,
                                     occurred_at=backdated_at)
    backdated.refresh_from_db()
    assert backdated.occurred_at == backdated_at


def test_integration_message_str_is_number_em_dash_document_type_label(integration_message_a):
    assert str(integration_message_a) == (
        f"{integration_message_a.number} {_integration_EM_DASH} 850 Purchase Order")


def test_integration_message_declares_the_msg_prefix_and_hides_the_column():
    assert IntegrationMessage.NUMBER_PREFIX == "MSG"
    assert _integration_field(IntegrationMessage, "number").editable is False


def test_integration_message_numbers_run_in_sequence_inside_one_workspace(
        tenant_a, integration_endpoint_a):
    first = _integration_message(tenant_a, integration_endpoint_a)
    second = _integration_message(tenant_a, integration_endpoint_a)
    assert [first.number, second.number] == ["MSG-00001", "MSG-00002"]


def test_integration_message_number_sequence_restarts_in_each_workspace(
        integration_message_a, integration_message_b):
    assert integration_message_a.number == integration_message_b.number == "MSG-00001"
    assert integration_message_a.tenant_id != integration_message_b.tenant_id


def test_integration_message_unique_together_is_the_number_pair_only(
        tenant_a, integration_endpoint_a):
    """A log has no name to constrain - two rows may legitimately be identical in every column but
    the number and the moment."""
    assert IntegrationMessage._meta.unique_together == (("tenant", "number"),)
    first = _integration_message(tenant_a, integration_endpoint_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _integration_message(tenant_a, integration_endpoint_a, number=first.number)


def test_integration_message_ordering_is_newest_first_with_an_id_tiebreak():
    assert IntegrationMessage._meta.ordering == ["-occurred_at", "-id"]


def test_integration_message_ties_on_occurred_at_are_broken_by_id(
        tenant_a, integration_endpoint_a):
    """A batch import lands many rows on the identical ``occurred_at``; without the tie-break page 2
    is whatever the database felt like returning."""
    moment = timezone.now() - datetime.timedelta(hours=5)
    first = _integration_message(tenant_a, integration_endpoint_a, occurred_at=moment)
    second = _integration_message(tenant_a, integration_endpoint_a, occurred_at=moment)
    ordered = list(IntegrationMessage.objects.filter(tenant=tenant_a, occurred_at=moment))
    assert ordered == [second, first]


def test_integration_message_declares_its_four_indexes():
    assert _integration_index_names(IntegrationMessage) == {
        "scm_msg_tnt_status_idx", "scm_msg_tnt_endpoint_idx", "scm_msg_tnt_extid_idx",
        "scm_msg_tnt_occat_idx"}


def test_integration_message_status_index_covers_the_exceptions_sort():
    """``integration_exceptions`` filters tenant+status and then sorts on ``occurred_at``; the third
    column is what keeps that off a filesort."""
    index = next(i for i in IntegrationMessage._meta.indexes
                 if i.name == "scm_msg_tnt_status_idx")
    assert index.fields == ["tenant", "status", "occurred_at"]


# =================================================================================================
# 4.19.2 IntegrationMessage - the four vocabularies
# =================================================================================================
def test_integration_message_direction_choices():
    assert _integration_values(MESSAGE_DIRECTION_CHOICES) == ["inbound", "outbound"]


def test_integration_message_status_choices_keep_sent_apart_from_acknowledged():
    """"We put it on the wire" and "the partner confirmed it" are different facts - on an EDI
    programme that distinction IS the dispute."""
    assert _integration_values(MESSAGE_STATUS_CHOICES) == [
        "pending", "sent", "received", "acknowledged", "failed", "ignored"]


def test_integration_message_source_choices_are_the_soft_pointer_vocabulary():
    assert _integration_values(MESSAGE_SOURCE_CHOICES) == [
        "purchase_order", "goods_receipt", "sales_order", "shipment", "freight_invoice",
        "stock_move", "item", "trade_document", "return_authorization", "logistics_client", "none"]


def test_integration_message_document_type_choices_are_the_twenty_three_payload_kinds():
    values = _integration_values(DOCUMENT_TYPE_CHOICES)
    assert len(values) == 23
    assert values == [
        "edi_850", "edi_855", "edi_860", "edi_856", "edi_810", "edi_820", "edi_846", "edi_214",
        "edi_864", "edi_940", "edi_945", "edi_947", "edi_997", "order_import", "inventory_feed",
        "fulfilment_export", "item_export", "refund_sync", "customer_sync", "tag_read_batch",
        "scan_batch", "sensor_reading", "other"]


def test_integration_message_document_type_covers_the_thirteen_x12_sets():
    edi = [value for value in _integration_values(DOCUMENT_TYPE_CHOICES)
           if value.startswith("edi_")]
    assert len(edi) == 13
    assert "edi_997" in edi, "the functional acknowledgement is what `acknowledges` chains"


@pytest.mark.parametrize("field, vocabulary", [
    ("direction", MESSAGE_DIRECTION_CHOICES),
    ("document_type", DOCUMENT_TYPE_CHOICES),
    ("status", MESSAGE_STATUS_CHOICES),
    ("source", MESSAGE_SOURCE_CHOICES),
])
def test_integration_message_choice_columns_are_wide_enough(field, vocabulary):
    column = _integration_field(IntegrationMessage, field)
    assert column.choices == vocabulary
    assert column.max_length >= max(len(value) for value in _integration_values(vocabulary))


# =================================================================================================
# 4.19.2 IntegrationMessage - the append-only shape
# =================================================================================================
def test_integration_message_external_id_is_deliberately_not_unique(
        tenant_a, integration_endpoint_a):
    """A redelivery is a fact worth RECORDING, not an insert worth refusing - and a partner reusing
    an id across document types would otherwise start losing rows silently."""
    assert _integration_field(IntegrationMessage, "external_id").unique is False
    duplicate = "evt_c8a0d4b2-1f77-42de-9c05-6b1e83f5aa10"
    _integration_message(tenant_a, integration_endpoint_a, external_id=duplicate)
    _integration_message(tenant_a, integration_endpoint_a, external_id=duplicate)
    assert IntegrationMessage.objects.filter(tenant=tenant_a, external_id=duplicate).count() == 2


@pytest.mark.parametrize("field", ["number", "attempt_count", "occurred_at", "acknowledged_at"])
def test_integration_message_system_columns_are_editable_false(field):
    """There is no ModelForm for this model at all, and these four are the columns that must stay
    unreachable even if one were ever added (L22)."""
    assert _integration_field(IntegrationMessage, field).editable is False


def test_integration_message_attempt_count_is_assignable_at_create_only(
        integration_message_failed_a):
    """``reprocess`` is its only other writer (+1 per accepted press); the seeder reaches it here."""
    assert integration_message_failed_a.attempt_count == 3


def test_integration_message_record_count_is_a_batch_size_not_a_row_count(
        integration_message_failed_a):
    """A tag-read batch of 4,200 reads is ONE row - a log that grows with the traffic it describes
    stops being readable exactly when it matters."""
    assert integration_message_failed_a.record_count == 4200
    assert IntegrationMessage.objects.filter(
        tenant=integration_message_failed_a.tenant_id,
        document_type="tag_read_batch").count() == 1


def test_integration_message_carries_no_generic_foreign_key():
    """The app bans it (``ColdChainMonitors.py:18``): a ``(content_type, object_id)`` pair cannot be
    tenant-joined, so every "does this row belong to this workspace" query degrades to Python."""
    names = _integration_field_names(IntegrationMessage)
    assert "content_type" not in names and "object_id" not in names


def test_integration_message_correlation_is_a_soft_pointer_plus_two_typed_fks():
    names = _integration_field_names(IntegrationMessage)
    assert {"source", "source_reference", "purchase_order", "sales_order"} <= names
    typed = {f.name for f in IntegrationMessage._meta.fields
             if f.is_relation and f.name not in {"tenant", "endpoint", "acknowledges"}}
    assert typed == {"purchase_order", "sales_order"}


def test_integration_message_soft_pointer_carries_the_referenced_document_number(
        integration_message_a, purchase_order_a):
    assert integration_message_a.source == "purchase_order"
    assert integration_message_a.source_reference == purchase_order_a.number
    assert integration_message_a.purchase_order_id == purchase_order_a.id


# =================================================================================================
# 4.19.2 IntegrationMessage - relational rules
# =================================================================================================
def test_integration_message_endpoint_cascades(tenant_a, integration_endpoint_a):
    """A log line has no life of its own without the connection it crossed - and an orphan would
    leave the exceptions cockpit grouping failures under a connection that no longer exists."""
    assert _integration_field(
        IntegrationMessage, "endpoint").remote_field.on_delete is models.CASCADE
    _integration_message(tenant_a, integration_endpoint_a)
    _integration_message(tenant_a, integration_endpoint_a)
    integration_endpoint_a.delete()
    assert IntegrationMessage.objects.filter(tenant=tenant_a).count() == 0


def test_integration_message_endpoint_related_name_is_messages(
        integration_message_a, integration_endpoint_edi_a):
    assert list(integration_endpoint_edi_a.messages.all()) == [integration_message_a]


def test_integration_message_acknowledges_is_set_null(
        integration_message_a, integration_message_ack_a):
    """An acknowledgement outlives what it acknowledged - losing the answered row must not delete
    the proof that the partner answered."""
    assert _integration_field(
        IntegrationMessage, "acknowledges").remote_field.on_delete is models.SET_NULL
    integration_message_a.delete()
    integration_message_ack_a.refresh_from_db()
    assert integration_message_ack_a.acknowledges_id is None
    assert integration_message_ack_a.pk is not None


def test_integration_message_acknowledgement_chain_reads_both_ways(
        integration_message_a, integration_message_ack_a):
    assert integration_message_ack_a.acknowledges_id == integration_message_a.pk
    assert list(integration_message_a.acknowledged_by.all()) == [integration_message_ack_a]


@pytest.mark.parametrize("field", ["purchase_order", "sales_order"])
def test_integration_message_typed_document_fks_are_set_null(field):
    column = _integration_field(IntegrationMessage, field)
    assert column.remote_field.on_delete is models.SET_NULL
    assert column.null is True and column.blank is True


def test_integration_message_names_its_four_tenant_scoped_fks():
    assert IntegrationMessage.TENANT_SCOPED_FKS == (
        "endpoint", "acknowledges", "purchase_order", "sales_order")


@pytest.mark.parametrize("field, fixture_name", [
    ("endpoint", "integration_endpoint_b"),
    ("acknowledges", "integration_message_b"),
    ("purchase_order", "purchase_order_b"),
    ("sales_order", "sales_order_b"),
])
def test_integration_message_clean_rejects_a_cross_tenant_fk(
        request, tenant_a, integration_endpoint_a, field, fixture_name):
    foreign = request.getfixturevalue(fixture_name)
    kwargs = {"tenant": tenant_a, "endpoint": integration_endpoint_a, "direction": "inbound"}
    kwargs[field] = foreign
    errors = _integration_clean_errors(IntegrationMessage(**kwargs))
    assert set(errors) == {field}
    assert errors[field] == ["That record belongs to another workspace."]


def test_integration_message_clean_accepts_a_same_tenant_chain(integration_message_ack_a):
    assert integration_message_ack_a.clean() is None


def test_integration_message_clean_rejects_self_acknowledgement(integration_message_a):
    """Checked against the pk rather than the object, so it holds on an admin edit of a saved
    row."""
    integration_message_a.acknowledges = integration_message_a
    errors = _integration_clean_errors(integration_message_a)
    assert set(errors) == {"acknowledges"}
    assert "cannot acknowledge itself" in errors["acknowledges"][0]


def test_integration_message_clean_is_skipped_while_the_row_has_no_tenant(
        integration_endpoint_b):
    assert IntegrationMessage(endpoint=integration_endpoint_b, direction="inbound").clean() is None


# =================================================================================================
# 4.19.2 IntegrationMessage - the counters the pages render are AGGREGATES (L29)
# =================================================================================================
def test_integration_message_totals_are_not_stored_on_the_endpoint(
        integration_message_a, integration_message_ack_a, integration_endpoint_edi_a):
    """The endpoint detail page's ``message_stats`` is one ``.aggregate()`` over this table - there
    is no denormalised counter to drift."""
    names = _integration_field_names(IntegrationEndpoint)
    assert names.isdisjoint({"message_count", "messages_count", "failed_count", "sent_count",
                             "acknowledged_count", "total_messages", "error_count"})
    stats = IntegrationMessage.objects.filter(
        tenant=integration_endpoint_edi_a.tenant_id, endpoint=integration_endpoint_edi_a
    ).aggregate(total=Count("id"),
                received=Count("id", filter=Q(status="received")),
                sent=Count("id", filter=Q(status="sent")))
    assert stats == {"total": 2, "received": 1, "sent": 1}


def test_integration_message_exception_rollup_is_a_query_not_a_table(
        tenant_a, integration_message_failed_a, integration_message_failed_http_a):
    """``error_groups`` is ``.values('error_code').annotate(Count, Count(distinct))`` - the cockpit
    stores nothing of its own."""
    groups = list(
        IntegrationMessage.objects.filter(tenant=tenant_a, status="failed")
        .order_by().values("error_code")
        .annotate(count=Count("id"), endpoint_count=Count("endpoint", distinct=True))
        .order_by("-count", "error_code"))
    assert groups == [
        {"error_code": "HTTP_429", "count": 1, "endpoint_count": 1},
        {"error_code": "LLRP_TIMEOUT", "count": 1, "endpoint_count": 1},
    ]


def test_integration_message_exception_totals_read_the_whole_failure_set(
        tenant_a, integration_message_a, integration_message_failed_a,
        integration_message_failed_http_a):
    failures = IntegrationMessage.objects.filter(tenant=tenant_a, status="failed")
    assert failures.count() == 2
    assert failures.values("endpoint").distinct().count() == 2
    assert failures.values("error_code").distinct().count() == 2


def test_integration_message_a_failure_in_another_workspace_is_never_counted(
        tenant_a, integration_message_failed_a, integration_message_b):
    assert IntegrationMessage.objects.filter(tenant=tenant_a, status="failed").count() == 1


# =================================================================================================
# 4.19.3 WebhookSubscription [WHK-] - defaults
# =================================================================================================
@pytest.mark.parametrize("field, expected", [
    ("trigger_event", "created"),
    ("payload_format", "json"),
    ("auto_disable_threshold", 8),
    ("is_active", True),
    ("consecutive_failures", 0),
    ("filter_expression", ""),
    ("include_fields", ""),
    ("description", ""),
    ("signing_secret_prefix", ""),
    ("signing_secret_hash", ""),
])
def test_integration_subscription_minimal_row_takes_its_documented_default(
        tenant_a, field, expected):
    subscription = _integration_subscription(tenant_a, "Minimal rule")
    assert getattr(subscription, field) == expected


def test_integration_subscription_minimal_row_has_no_last_delivery(tenant_a):
    assert _integration_subscription(tenant_a, "Minimal rule").last_delivery_at is None


def test_integration_subscription_headers_default_to_an_empty_dict_per_instance(tenant_a):
    """``default=dict``, never ``default={}`` - a shared mutable default would let one row's headers
    leak into the next."""
    assert _integration_field(WebhookSubscription, "headers").default is dict
    first = _integration_subscription(tenant_a, "Headers one")
    second = _integration_subscription(tenant_a, "Headers two")
    assert first.headers == second.headers == {}
    assert first.headers is not second.headers


def test_integration_subscription_headers_round_trip_as_a_flat_string_map(
        integration_subscription_a):
    integration_subscription_a.refresh_from_db()
    assert integration_subscription_a.headers == {"X-Source": "NavERP"}


@pytest.mark.parametrize("field", ["trigger_entity", "target_url"])
def test_integration_subscription_required_columns_have_no_default(tenant_a, field):
    assert _integration_field(WebhookSubscription, field).has_default() is False
    blank = WebhookSubscription(tenant=tenant_a, name="Missing input")
    assert field in _integration_full_clean_errors(blank)


def test_integration_subscription_str_is_number_em_dash_name(integration_subscription_a):
    assert str(integration_subscription_a) == (
        f"{integration_subscription_a.number} {_integration_EM_DASH} "
        f"{integration_subscription_a.name}")


def test_integration_subscription_declares_the_whk_prefix_and_hides_the_column():
    assert WebhookSubscription.NUMBER_PREFIX == "WHK"
    assert _integration_field(WebhookSubscription, "number").editable is False


def test_integration_subscription_numbers_run_in_sequence_inside_one_workspace(tenant_a):
    first = _integration_subscription(tenant_a, "Rule one")
    second = _integration_subscription(tenant_a, "Rule two")
    assert [first.number, second.number] == ["WHK-00001", "WHK-00002"]


def test_integration_subscription_number_sequence_restarts_in_each_workspace(
        integration_subscription_a, integration_subscription_b):
    assert integration_subscription_a.number == integration_subscription_b.number == "WHK-00001"
    assert integration_subscription_a.tenant_id != integration_subscription_b.tenant_id


def test_integration_subscription_unique_together_names_both_pairs():
    assert WebhookSubscription._meta.unique_together == (
        ("tenant", "number"), ("tenant", "name"))


def test_integration_subscription_duplicate_name_in_one_workspace_is_refused(
        tenant_a, integration_subscription_a):
    """Two rules with the same name in one workspace is an operator looking at a list unable to tell
    which one they are editing."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _integration_subscription(tenant_a, integration_subscription_a.name)


def test_integration_subscription_two_workspaces_may_share_a_name(
        tenant_b, integration_subscription_a):
    twin = _integration_subscription(tenant_b, integration_subscription_a.name)
    assert twin.name == integration_subscription_a.name
    assert twin.tenant_id != integration_subscription_a.tenant_id


def test_integration_subscription_ordering_is_a_total_order():
    assert WebhookSubscription._meta.ordering == ["name", "id"]


def test_integration_subscription_declares_its_two_indexes():
    assert _integration_index_names(WebhookSubscription) == {
        "scm_whk_tnt_active_idx", "scm_whk_tnt_entity_idx"}


# =================================================================================================
# 4.19.3 WebhookSubscription - the three vocabularies and the missing fourth
# =================================================================================================
def test_integration_subscription_entity_choices_are_supply_chain_not_crm():
    """``crm.Webhook``'s vocabulary is lead/opportunity/case and cannot express
    ``shipment.delivered`` - a documented decision, not drift."""
    assert _integration_values(WEBHOOK_ENTITY_CHOICES) == [
        "purchase_order", "goods_receipt", "sales_order", "shipment", "stock_move",
        "return_authorization", "quality_inspection", "work_order", "asset",
        "supply_chain_alert"]


def test_integration_subscription_event_choices_keep_status_changed_apart_from_updated():
    assert _integration_values(WEBHOOK_EVENT_CHOICES) == [
        "created", "updated", "status_changed", "approved", "posted", "cancelled", "delivered"]


def test_integration_subscription_payload_format_choices():
    assert _integration_values(PAYLOAD_FORMAT_CHOICES) == ["json", "xml"]


@pytest.mark.parametrize("field, vocabulary", [
    ("trigger_entity", WEBHOOK_ENTITY_CHOICES),
    ("trigger_event", WEBHOOK_EVENT_CHOICES),
    ("payload_format", PAYLOAD_FORMAT_CHOICES),
])
def test_integration_subscription_choice_columns_are_wide_enough(field, vocabulary):
    column = _integration_field(WebhookSubscription, field)
    assert column.choices == vocabulary
    assert column.max_length >= max(len(value) for value in _integration_values(vocabulary))


def test_integration_subscription_has_no_status_column_at_all():
    """The list page's ``?status=active|inactive`` vocabulary is a VIEW-LOCAL literal translated
    onto ``is_active`` - asserting a model column here would be asserting a field that must not
    exist."""
    assert "status" not in _integration_field_names(WebhookSubscription)
    assert _integration_field(WebhookSubscription, "is_active").default is True


def test_integration_subscription_every_entity_choice_names_a_real_scm_class():
    """Every member was grepped as an existing class at build time; a vocabulary that names a table
    nobody can fire from is a dropdown entry that never matches."""
    import apps.scm.models as package
    class_names = {
        "purchase_order": "PurchaseOrder", "goods_receipt": "GoodsReceiptNote",
        "sales_order": "SalesOrder", "shipment": "Shipment", "stock_move": "StockMove",
        "return_authorization": "ReturnAuthorization", "quality_inspection": "QualityInspection",
        "work_order": "WorkOrder", "asset": "Asset", "supply_chain_alert": "SupplyChainAlert",
    }
    for value in _integration_values(WEBHOOK_ENTITY_CHOICES):
        assert hasattr(package, class_names[value]), f"{value} names no scm class"


# =================================================================================================
# 4.19.3 WebhookSubscription - target_url, the threshold and the missing FKs
# =================================================================================================
def test_integration_subscription_target_url_is_a_urlfield():
    """Unlike ``IntegrationEndpoint.endpoint_url``: a webhook target really is HTTP(S), so
    URLValidator's scheme restriction excludes nothing legitimate."""
    column = _integration_field(WebhookSubscription, "target_url")
    assert isinstance(column, models.URLField)
    assert column.max_length == 500


def test_integration_subscription_target_url_rejects_a_non_url(tenant_a):
    subscription = _integration_subscription(tenant_a, "Bad target")
    subscription.target_url = "not a url"
    assert "target_url" in _integration_full_clean_errors(subscription)


@pytest.mark.parametrize("threshold", [1, 8, 20])
def test_integration_subscription_accepts_a_threshold_inside_the_bounds(tenant_a, threshold):
    subscription = _integration_subscription(tenant_a, f"Threshold {threshold}",
                                             auto_disable_threshold=threshold)
    subscription.full_clean()


@pytest.mark.parametrize("threshold", [0, 21, 255])
def test_integration_subscription_refuses_a_threshold_outside_the_bounds(tenant_a, threshold):
    """Bounded 1..20 so a typo cannot describe a retry policy nobody would run."""
    subscription = _integration_subscription(tenant_a, f"Threshold {threshold}")
    subscription.auto_disable_threshold = threshold
    assert "auto_disable_threshold" in _integration_full_clean_errors(subscription)


def test_integration_subscription_has_no_foreign_key_beyond_the_tenant():
    """A subscription is a rule about INTERNAL events and points at no partner, party or document -
    which is why ``TENANT_SCOPED_FKS`` is empty and there is no ``clean()`` on the class."""
    relations = [f.name for f in WebhookSubscription._meta.fields if f.is_relation]
    assert relations == ["tenant"]
    assert WebhookSubscription.TENANT_SCOPED_FKS == ()
    assert WebhookSubscription.clean is models.Model.clean


@pytest.mark.parametrize("field", ["number", "consecutive_failures", "last_delivery_at",
                                   "signing_secret_prefix", "signing_secret_hash"])
def test_integration_subscription_system_columns_are_editable_false(field):
    assert _integration_field(WebhookSubscription, field).editable is False


def test_integration_subscription_failure_counter_is_recorded_never_enforced(
        integration_subscription_inactive_a):
    """Nothing in this pass increments it, because nothing delivers - the threshold is advice, not
    an enforced switch."""
    assert integration_subscription_inactive_a.consecutive_failures == 4
    assert integration_subscription_inactive_a.auto_disable_threshold == 4
    assert integration_subscription_inactive_a.is_active is False


# =================================================================================================
# 4.19.3 WebhookSubscription - the signing-secret MARKER
# =================================================================================================
def test_integration_subscription_masked_is_blank_without_a_secret(integration_subscription_a):
    assert integration_subscription_a.signing_secret_hash == ""
    assert integration_subscription_a.masked == ""


def test_integration_subscription_masked_is_prefix_plus_eight_bullets(
        integration_subscription_with_secret_a):
    assert integration_subscription_with_secret_a.masked == (
        "whk-plai" + _integration_BULLET * 8)


def test_integration_subscription_masked_is_derived_not_stored():
    assert "masked" not in _integration_field_names(WebhookSubscription)
    assert isinstance(WebhookSubscription.masked, property)


def test_integration_subscription_set_signing_secret_writes_prefix_and_hash(tenant_a):
    subscription = WebhookSubscription(
        tenant=tenant_a, name="Secret writer", trigger_entity="shipment",
        target_url="https://example.com/hook")
    subscription.set_signing_secret("whk-plaintext-0123456789")
    subscription.save()
    subscription.refresh_from_db()
    assert subscription.signing_secret_prefix == "whk-plai"
    assert subscription.signing_secret_hash == WebhookSubscription.hash_secret(
        "whk-plaintext-0123456789")


def test_integration_subscription_hash_secret_is_sha256():
    assert WebhookSubscription.hash_secret("whk-plaintext-0123456789") == (
        hashlib.sha256(b"whk-plaintext-0123456789").hexdigest())


def test_integration_subscription_and_endpoint_hash_the_same_way():
    """Two copies of one rule is two places for it to be wrong - both are plain SHA-256 hex."""
    assert (WebhookSubscription.hash_secret("shared-input") ==
            IntegrationEndpoint.hash_secret("shared-input"))


def test_integration_subscription_generate_secret_is_from_the_csprng():
    minted = {WebhookSubscription.generate_secret() for _ in range(64)}
    assert len(minted) == 64
    assert all(len(value) >= 30 for value in minted)


def test_integration_subscription_plaintext_secret_is_never_persisted(
        integration_subscription_with_secret_a):
    plaintext = "whk-plaintext-0123456789"
    stored = _integration_stored_text(integration_subscription_with_secret_a)
    assert all(plaintext not in value for value in stored)


def test_integration_subscription_rotating_the_secret_changes_the_hash(tenant_a):
    subscription = _integration_subscription(tenant_a, "Rotation")
    subscription.set_signing_secret("first-signing-secret")
    subscription.save()
    before = subscription.signing_secret_hash
    subscription.set_signing_secret("second-signing-secret")
    subscription.save()
    assert subscription.signing_secret_hash != before
    assert subscription.signing_secret_prefix == "second-s"


# =================================================================================================
# 4.19.4 WebhookDelivery - unnumbered, append-only telemetry
# =================================================================================================
def test_integration_delivery_is_tenant_owned_and_not_numbered():
    """Human-discussed records get a number; per-attempt telemetry does not - the same side of that
    line as ``StockMove``, ``TemperatureReading`` and ``PortalActivity``."""
    assert issubclass(WebhookDelivery, TenantOwned)
    assert not issubclass(WebhookDelivery, TenantNumbered)
    assert "number" not in _integration_field_names(WebhookDelivery)
    assert getattr(WebhookDelivery, "NUMBER_PREFIX", "") == ""


def test_integration_delivery_declares_no_unique_together_at_all():
    """There is no natural key: the same subscription genuinely does retry the same event, which is
    what ``attempt_no`` is for."""
    assert WebhookDelivery._meta.unique_together == ()


@pytest.mark.parametrize("field, expected", [
    ("status", "pending"),
    ("attempt_no", 1),
    ("payload_excerpt", ""),
    ("signature", ""),
    ("error_message", ""),
])
def test_integration_delivery_minimal_row_takes_its_documented_default(
        tenant_a, integration_subscription_a, field, expected):
    delivery = _integration_delivery(tenant_a, integration_subscription_a)
    assert getattr(delivery, field) == expected


def test_integration_delivery_response_code_is_nullable_not_zero_defaulted(
        tenant_a, integration_subscription_a):
    """"The partner answered 000" and "we never got an answer" are different facts, and a log that
    cannot tell them apart is not much of a log."""
    delivery = _integration_delivery(tenant_a, integration_subscription_a)
    assert delivery.response_code is None
    assert delivery.next_attempt_at is None
    column = _integration_field(WebhookDelivery, "response_code")
    assert column.null is True and column.has_default() is False


def test_integration_delivery_signature_is_blank_on_every_row_this_pass_creates(
        integration_delivery_a, integration_delivery_success_a):
    """There is no plaintext signing key (only a prefix+hash marker) and no transport, so nothing
    can compute one. The column is the home for a future pass - not a bug."""
    assert integration_delivery_a.signature == ""
    assert integration_delivery_success_a.signature == ""


def test_integration_delivery_event_has_no_default(tenant_a, integration_subscription_a):
    assert _integration_field(WebhookDelivery, "event").has_default() is False
    blank = WebhookDelivery(tenant=tenant_a, subscription=integration_subscription_a)
    assert "event" in _integration_full_clean_errors(blank)


def test_integration_delivery_event_is_denormalised_from_the_rule(
        integration_delivery_a, integration_subscription_a):
    """Editing the rule afterwards must not silently rewrite what an already-recorded attempt was an
    attempt AT."""
    assert integration_delivery_a.event == "shipment.delivered"
    integration_subscription_a.trigger_event = "created"
    integration_subscription_a.save(update_fields=["trigger_event"])
    integration_delivery_a.refresh_from_db()
    assert integration_delivery_a.event == "shipment.delivered"


def test_integration_delivery_str_is_event_hash_attempt(integration_delivery_a):
    assert str(integration_delivery_a) == "shipment.delivered #3"


def test_integration_delivery_ordering_is_newest_first_with_an_id_tiebreak():
    assert WebhookDelivery._meta.ordering == ["-triggered_at", "-id"]


def test_integration_delivery_ties_on_triggered_at_are_broken_by_id(
        tenant_a, integration_subscription_a):
    moment = timezone.now() - datetime.timedelta(minutes=7)
    first = _integration_delivery(tenant_a, integration_subscription_a, triggered_at=moment)
    second = _integration_delivery(tenant_a, integration_subscription_a, triggered_at=moment)
    assert list(WebhookDelivery.objects.filter(tenant=tenant_a, triggered_at=moment)) == [
        second, first]


def test_integration_delivery_declares_its_three_scm_prefixed_indexes():
    """Index names are GLOBAL to the database - crm's own ``WebhookDelivery`` already owns
    ``crm_whd_tnt_*``."""
    assert _integration_index_names(WebhookDelivery) == {
        "scm_whd_tnt_sub_idx", "scm_whd_tnt_status_idx", "scm_whd_tnt_trigat_idx"}


def test_integration_delivery_triggered_at_defaults_to_now_and_is_assignable(
        tenant_a, integration_subscription_a):
    assert _integration_field(WebhookDelivery, "triggered_at").default is timezone.now
    assert _integration_field(WebhookDelivery, "triggered_at").editable is False
    moment = timezone.now() - datetime.timedelta(days=4)
    delivery = _integration_delivery(tenant_a, integration_subscription_a, triggered_at=moment)
    delivery.refresh_from_db()
    assert delivery.triggered_at == moment


def test_integration_delivery_status_choices_include_the_honest_simulated_member():
    """4.19 ships no outbound HTTP, so a row that never left the process is neither a success nor a
    failure - recording it as ``success`` would make the log evidence of something that did not
    happen."""
    assert _integration_values(DELIVERY_STATUS_CHOICES) == [
        "pending", "success", "failed", "exhausted", "simulated"]
    column = _integration_field(WebhookDelivery, "status")
    assert column.max_length >= max(
        len(value) for value in _integration_values(DELIVERY_STATUS_CHOICES))


def test_integration_delivery_subscription_cascades(tenant_a, integration_subscription_a):
    """An attempt log with no rule is telemetry about nothing."""
    assert _integration_field(
        WebhookDelivery, "subscription").remote_field.on_delete is models.CASCADE
    _integration_delivery(tenant_a, integration_subscription_a)
    _integration_delivery(tenant_a, integration_subscription_a)
    integration_subscription_a.delete()
    assert WebhookDelivery.objects.filter(tenant=tenant_a).count() == 0


def test_integration_delivery_related_name_is_deliveries(
        integration_delivery_a, integration_delivery_success_a, integration_subscription_a):
    assert set(integration_subscription_a.deliveries.all()) == {
        integration_delivery_a, integration_delivery_success_a}


def test_integration_delivery_names_its_one_tenant_scoped_fk():
    assert WebhookDelivery.TENANT_SCOPED_FKS == ("subscription",)


def test_integration_delivery_clean_rejects_a_cross_tenant_subscription(
        tenant_a, integration_subscription_b):
    delivery = WebhookDelivery(tenant=tenant_a, subscription=integration_subscription_b,
                               event="sales_order.created")
    errors = _integration_clean_errors(delivery)
    assert set(errors) == {"subscription"}
    assert errors["subscription"] == ["That record belongs to another workspace."]


def test_integration_delivery_clean_accepts_a_same_tenant_subscription(integration_delivery_a):
    assert integration_delivery_a.clean() is None


def test_integration_delivery_clean_is_skipped_while_the_row_has_no_tenant(
        integration_subscription_b):
    assert WebhookDelivery(subscription=integration_subscription_b,
                           event="sales_order.created").clean() is None


# =================================================================================================
# 4.19.4 WebhookDelivery - the published backoff schedule, DERIVED not typed
# =================================================================================================
def test_integration_delivery_backoff_schedule_is_svix_verbatim():
    """A backoff curve is one of the few things in webhook delivery with a de-facto industry answer;
    a home-grown one is a number nobody can reason about when a partner asks."""
    assert DELIVERY_BACKOFF_SECONDS == (0, 5, 300, 1800, 7200, 18000, 36000, 36000)
    assert isinstance(DELIVERY_BACKOFF_SECONDS, tuple), "a list would be mutable at import time"


def test_integration_delivery_max_attempts_is_derived_from_the_schedule():
    """Derived from ``len()`` rather than typed, so widening the schedule cannot leave a stale
    ceiling behind it."""
    assert WebhookDelivery.MAX_ATTEMPTS == len(DELIVERY_BACKOFF_SECONDS) == 8
    assert "max_attempts" not in _integration_field_names(WebhookDelivery)


@pytest.mark.parametrize("attempt_no, expected", [
    (0, 0),
    (1, 5),
    (2, 300),
    (3, 1800),
    (4, 7200),
    (5, 18000),
    (6, 36000),
    (7, 36000),
    (8, None),
    (9, None),
])
def test_integration_delivery_next_backoff_seconds_walks_the_schedule(attempt_no, expected):
    """Attempt N has already consumed slot N-1, so the NEXT slot is index ``attempt_no`` itself."""
    assert WebhookDelivery(attempt_no=attempt_no).next_backoff_seconds == expected


def test_integration_delivery_next_backoff_seconds_is_derived_not_stored():
    assert "next_backoff_seconds" not in _integration_field_names(WebhookDelivery)
    assert isinstance(WebhookDelivery.next_backoff_seconds, property)


def test_integration_delivery_a_retryable_row_reports_its_next_slot(integration_delivery_a):
    assert integration_delivery_a.attempt_no == 3
    assert integration_delivery_a.next_backoff_seconds == 1800


def test_integration_delivery_a_spent_row_reports_no_slot(integration_delivery_final_a):
    """Returning ``None`` - rather than raising or clamping to the last slot - is what tells the
    retry view to mark the row ``exhausted`` instead of scheduling an attempt the published schedule
    does not describe."""
    assert integration_delivery_final_a.attempt_no == WebhookDelivery.MAX_ATTEMPTS
    assert integration_delivery_final_a.next_backoff_seconds is None


def test_integration_delivery_a_negative_attempt_number_does_not_read_the_last_slot():
    """A raw import could set ``attempt_no`` to something absurd; a negative index would silently
    return the 10-hour slot rather than fail."""
    assert WebhookDelivery(attempt_no=-1).next_backoff_seconds is None


# =================================================================================================
# 4.19.4 WebhookDelivery - the panel counters are AGGREGATES over this table (L29)
# =================================================================================================
def test_integration_delivery_stats_are_not_stored_on_the_subscription(
        integration_delivery_a, integration_delivery_success_a, integration_subscription_a):
    names = _integration_field_names(WebhookSubscription)
    assert names.isdisjoint({"delivery_count", "deliveries_count", "success_count",
                             "failure_count", "total_deliveries", "exhausted_count"})
    stats = integration_subscription_a.deliveries.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending")),
        success=Count("id", filter=Q(status="success")),
        failed=Count("id", filter=Q(status="failed")),
        exhausted=Count("id", filter=Q(status="exhausted")),
        simulated=Count("id", filter=Q(status="simulated")))
    assert stats == {"total": 2, "pending": 0, "success": 1, "failed": 1, "exhausted": 0,
                     "simulated": 0}


def test_integration_delivery_another_workspace_never_reaches_the_aggregate(
        tenant_a, integration_delivery_a, integration_delivery_b):
    assert WebhookDelivery.objects.filter(tenant=tenant_a).count() == 1
    assert WebhookDelivery.objects.filter(tenant=tenant_a, status="failed").aggregate(
        total=Count("id"))["total"] == 1
