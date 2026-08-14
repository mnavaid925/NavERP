"""SCM 4.17 Third-Party Logistics (3PL) Management — MODEL invariants.

Six tables: ``LogisticsClient`` [3PL-] (the depositor master), ``ClientRateCard`` [TAR-] +
``ClientRateCardLine`` (the tariff), ``ClientBillingRun`` [CBR-] + ``ClientBillingRunLine`` (the
period calculation) and ``ClientSLA`` [SLA-] (the promise plus the evidence for it).

What this lane pins, in the order the sub-module's own docstrings state it:

* **per-tenant auto-numbers** — the four prefixes mint, run in sequence inside a workspace and
  RESTART in the next one, because ``unique_together ("tenant", "number")`` is what makes two
  workspaces both legitimately hold a ``3PL-00001``;
* **defaults and the closed vocabularies** — every CHOICES value, both CSS registries (colour-named
  classes only — a ``badge-success`` renders unstyled, L33) and the ``SLA_METRIC_META`` registry,
  which is validated against rather than suggested;
* **every figure that is DERIVED rather than stored** (L29) — the client's six stock/SLA reads are
  METHODS firing their own aggregate and are not columns; a rate card's active line count is a
  query; a run's ``subtotal``/``minimum_adjustment``/``total`` are ``editable=False`` with
  ``recalc_amounts()`` as their only writer; a run line's ``amount`` is written by ``save()`` and by
  nobody else; and the SLA's eight evidence columns are written only by ``recompute()``;
* **the two tenant-LESS children** — ``ClientRateCardLine`` and ``ClientBillingRunLine`` carry no
  tenant column at all and are reachable only through their parent;
* **the verb ladders** — a run that was never calculated cannot be approved, one that was never
  approved cannot be invoiced, an invoiced one cannot be voided (L35), and ``no_data`` is never
  written as a confident zero.

Fixtures come from ``apps/scm/tests/conftest.py`` (the ``tpl_`` block) and the ROOT ``conftest.py``.
Nothing here writes to either. Every date is derived from ``timezone.localdate()`` or INJECTED as an
``as_of`` argument — never ``datetime.date.today()`` (L16).

NAMING: test functions are ``test_3pl_*`` and module-level helpers ``_3pl_*`` (both legal — only the
FIRST character of an identifier may not be a digit), while the conftest FIXTURES carry ``tpl_``
because ``3pl_client_a`` is not a legal identifier. The two conventions differ on purpose.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.scm.models import (
    BILLING_CYCLE_CHOICES,
    CHARGE_BASIS_CHOICES,
    CHARGE_CATEGORY_CHOICES,
    CHARGE_CATEGORY_CSS,
    CLIENT_STATUS_CHOICES,
    CLIENT_STATUS_CSS,
    COMMITTED_SPACE_MODELS,
    EDITABLE_RATE_CARD_STATUSES,
    EDITABLE_RUN_STATUSES,
    INTEGRATION_MODE_CHOICES,
    MANUAL_ONLY_BASES,
    MAX_CLIENT_DEPTH,
    MAX_COMMITTED_PALLETS,
    MAX_COMMITTED_SQFT,
    MAX_MEASUREMENT_ROWS,
    MAX_RATE_CARD_LINES,
    MAX_RUN_LINES,
    MAX_RUN_PERIOD_DAYS,
    PERIODIC_BASES,
    RATE_CARD_STATUS_CHOICES,
    RATE_CARD_STATUS_CSS,
    RATE_PERIOD_CHOICES,
    RUN_STATUS_CHOICES,
    RUN_STATUS_CSS,
    SLA_DIRECTION_CHOICES,
    SLA_METRIC_CHOICES,
    SLA_METRIC_META,
    SLA_STATUS_CHOICES,
    SLA_STATUS_CSS,
    SLA_UNIT_CHOICES,
    SLA_WINDOW_CHOICES,
    SPACE_MODEL_CHOICES,
    STORAGE_BILLING_METHOD_CHOICES,
    ClientBillingRun,
    ClientBillingRunLine,
    ClientRateCard,
    ClientRateCardLine,
    ClientSLA,
    LogisticsClient,
)

pytestmark = pytest.mark.django_db


# =================================================================================================
# Helpers — every module-level name here is `_3pl_`-prefixed so a neighbouring sub-module's file
# cannot shadow it (the suite-hygiene guard checks the same thing per file).
# =================================================================================================

#: The only badge classes that exist in ``static/css/theme.css``. A semantic ``badge-success`` /
#: ``badge-warning`` / ``badge-danger`` renders completely UNSTYLED (L33), which is why both 4.17
#: CSS registries are asserted against this set rather than merely for being non-empty.
_3pl_badge_classes = {"badge-green", "badge-red", "badge-amber", "badge-info", "badge-muted",
                      "badge-slate"}


def _3pl_values(choices):
    """Just the stored values of a CHOICES list — labels are prose and may be reworded."""
    return [value for value, _label in choices]


def _3pl_field(model, name):
    return model._meta.get_field(name)


def _3pl_field_names(model):
    return {field.name for field in model._meta.get_fields()}


def _3pl_party(tenant, name):
    """A fresh party — ``unique_together ("tenant", "party")`` means one agreement per company."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _3pl_make_client(tenant, code, **kwargs):
    """A minimal extra ``LogisticsClient``, with its own party so the unique triple holds."""
    party = kwargs.pop("party", None) or _3pl_party(tenant, f"{code} Depositor")
    return LogisticsClient.objects.create(tenant=tenant, party=party, code=code, **kwargs)


def _3pl_moment(day, hour=12):
    """Midday on ``day``, timezone-aware — where a ledger row lands inside a billed period."""
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, 0)))


def _3pl_stock_move(tenant, item, location, quantity, moved_at, move_type="receipt"):
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, quantity=Decimal(quantity),
        unit_cost=Decimal("10.0000"), move_type=move_type, reference="TEST", moved_at=moved_at)


# =================================================================================================
# 4.17 · auto-numbers — prefix, per-tenant sequence, and no collision across workspaces
# =================================================================================================
def test_3pl_client_mints_a_3pl_number(tpl_client_a):
    assert tpl_client_a.number == "3PL-00001"


def test_3pl_client_numbers_run_in_sequence_inside_one_workspace(tpl_client_a, tpl_client_shared_a):
    assert [tpl_client_a.number, tpl_client_shared_a.number] == ["3PL-00001", "3PL-00002"]


def test_3pl_client_number_sequence_restarts_in_each_workspace(tpl_client_a, tpl_client_b):
    """``unique_together ("tenant", "number")`` — the counter is per tenant, so both workspaces
    legitimately hold a ``3PL-00001``."""
    assert tpl_client_a.number == tpl_client_b.number == "3PL-00001"
    assert tpl_client_a.tenant_id != tpl_client_b.tenant_id


def test_3pl_rate_card_mints_a_tar_number(tpl_rate_card_a):
    assert tpl_rate_card_a.number == "TAR-00001"


def test_3pl_rate_card_numbers_are_sequential(tpl_active_card_a, tpl_rate_card_a):
    assert [tpl_active_card_a.number, tpl_rate_card_a.number] == ["TAR-00001", "TAR-00002"]


def test_3pl_billing_run_mints_a_cbr_number(tpl_billing_run_a):
    assert tpl_billing_run_a.number == "CBR-00001"


def test_3pl_sla_mints_an_sla_number(tpl_sla_a):
    assert tpl_sla_a.number == "SLA-00001"


def test_3pl_sla_number_sequence_restarts_in_each_workspace(tpl_sla_a, tpl_sla_b):
    assert tpl_sla_a.number == tpl_sla_b.number == "SLA-00001"


@pytest.mark.parametrize("model, prefix", [
    (LogisticsClient, "3PL"),
    (ClientRateCard, "TAR"),
    (ClientBillingRun, "CBR"),
    (ClientSLA, "SLA"),
])
def test_3pl_numbered_models_declare_a_prefix_and_hide_the_column(model, prefix):
    """``number`` is ``editable=False`` on ``TenantNumbered``, which is what keeps it off every
    ModelForm automatically instead of relying on each form's field list (L22)."""
    assert model.NUMBER_PREFIX == prefix
    assert _3pl_field(model, "number").editable is False


@pytest.mark.parametrize("model", [ClientRateCardLine, ClientBillingRunLine])
def test_3pl_child_lines_carry_no_document_number_at_all(model):
    assert "number" not in _3pl_field_names(model)
    assert getattr(model, "NUMBER_PREFIX", "") == ""


def test_3pl_a_duplicate_client_number_inside_one_workspace_is_refused(tenant_a, tpl_client_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _3pl_make_client(tenant_a, "DUPN", number=tpl_client_a.number)


# =================================================================================================
# 4.17 · unique_together, always WITH the tenant
# =================================================================================================
def test_3pl_client_unique_together_names_all_three_pairs():
    assert LogisticsClient._meta.unique_together == (
        ("tenant", "number"), ("tenant", "code"), ("tenant", "party"))


def test_3pl_two_clients_in_one_workspace_may_not_share_a_code(tenant_a, tpl_client_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _3pl_make_client(tenant_a, tpl_client_a.code)


def test_3pl_two_workspaces_may_hold_the_same_client_code(tenant_a, tenant_b, tpl_client_a):
    other = _3pl_make_client(tenant_b, tpl_client_a.code)
    assert other.code == tpl_client_a.code
    assert other.tenant_id == tenant_b.id


def test_3pl_one_agreement_per_party(tenant_a, customer_a, tpl_client_a):
    """``("tenant", "party")`` is the business rule: two agreements for one company would make
    which tariff applied depend on row order."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _3pl_make_client(tenant_a, "SECOND", party=customer_a)


def test_3pl_rate_card_unique_together_pins_the_version(tenant_a, tpl_client_a, tpl_rate_card_a):
    assert ClientRateCard._meta.unique_together == (
        ("tenant", "number"), ("tenant", "client", "name", "version"))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ClientRateCard.objects.create(
                tenant=tenant_a, client=tpl_client_a, name=tpl_rate_card_a.name,
                version=tpl_rate_card_a.version,
                effective_from=tpl_rate_card_a.effective_from)


def test_3pl_a_second_version_of_the_same_tariff_name_is_allowed(tenant_a, tpl_client_a,
                                                                  tpl_rate_card_a):
    second = ClientRateCard.objects.create(
        tenant=tenant_a, client=tpl_client_a, name=tpl_rate_card_a.name, version=2,
        effective_from=tpl_rate_card_a.effective_from)
    assert second.version == 2


def test_3pl_billing_run_unique_together_pins_the_period(tenant_a, tpl_client_a, tpl_active_card_a,
                                                          tpl_billing_run_a, tpl_period):
    assert ClientBillingRun._meta.unique_together == (
        ("tenant", "number"), ("tenant", "client", "period_start", "period_end"))
    start, end = tpl_period
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ClientBillingRun.objects.create(
                tenant=tenant_a, client=tpl_client_a, rate_card=tpl_active_card_a,
                period_start=start, period_end=end)


def test_3pl_sla_unique_together_includes_the_scope(tenant_a, tpl_client_a, tpl_sla_a):
    assert ClientSLA._meta.unique_together == (
        ("tenant", "number"), ("tenant", "client", "metric", "scope_location"))


# =================================================================================================
# 4.17 · __str__ — including the guarded, unparented forms `write_audit_log` can hit
# =================================================================================================
def test_3pl_client_str_is_the_code_and_the_party(tpl_client_a):
    assert str(tpl_client_a) == "ACME · Acme Retail Customer"


def test_3pl_rate_card_str_leads_with_its_number_and_version(tpl_rate_card_a):
    assert str(tpl_rate_card_a) == f"{tpl_rate_card_a.number} · ACME v1"


def test_3pl_rate_card_str_survives_an_unparented_instance():
    assert str(ClientRateCard(version=3)) == "TAR · — v3"


def test_3pl_rate_card_line_str_names_its_parent(tpl_rate_card_line_a, tpl_rate_card_a):
    assert str(tpl_rate_card_line_a) == f"{tpl_rate_card_a.number} · Inbound receipt handling"


def test_3pl_billing_run_str_names_the_client_and_the_period(tpl_billing_run_a, tpl_period):
    start, end = tpl_period
    assert str(tpl_billing_run_a) == f"{tpl_billing_run_a.number} · ACME {start}–{end}"


def test_3pl_billing_run_str_survives_an_unparented_instance():
    run = ClientBillingRun(period_start=datetime.date(2026, 1, 1),
                           period_end=datetime.date(2026, 1, 31))
    assert str(run) == "CBR · ? 2026-01-01–2026-01-31"


def test_3pl_billing_run_line_str_is_the_description_and_the_amount(tpl_billing_run_line_a):
    assert str(tpl_billing_run_line_a) == "Kitting and rework labour · 50.00"


def test_3pl_sla_str_names_the_client_and_the_metric(tpl_sla_a):
    assert str(tpl_sla_a) == f"{tpl_sla_a.number} · ACME On-Time Shipment %"


def test_3pl_sla_str_survives_an_unparented_instance():
    assert str(ClientSLA(metric="otif_pct")) == "SLA · — OTIF %"


# =================================================================================================
# 4.17 · LogisticsClient — defaults every row inherits without anybody typing them
# =================================================================================================
def test_3pl_client_defaults_are_the_ones_the_contract_pins(tenant_a, tpl_customer_a2):
    client = LogisticsClient.objects.create(tenant=tenant_a, party=tpl_customer_a2, code="BARE")
    client.refresh_from_db()
    assert client.status == "prospect"
    assert client.billing_cycle == "monthly"
    assert client.billing_day == 1
    assert client.storage_billing_method == "calendar_month"
    assert client.minimum_monthly_charge == Decimal("0")
    assert client.default_tax_rate_pct == Decimal("0")
    assert client.space_model == "shared"
    assert client.committed_sqft == Decimal("0")
    assert client.committed_pallet_positions == 0
    assert client.notice_days == 0
    assert client.integration_mode == "none"
    assert client.parent_client_id is None
    assert client.notes == ""


def test_3pl_client_ships_with_no_onboarding_date_and_no_sync_stamp(tenant_a, tpl_customer_a2):
    """``last_synced_at`` is written by NOTHING in 4.17 — the column exists so 4.19's transport
    writes a real timestamp into a home that already exists."""
    client = LogisticsClient.objects.create(tenant=tenant_a, party=tpl_customer_a2, code="BARE")
    assert client.onboarded_on is None
    assert client.last_synced_at is None


def test_3pl_client_ordering_is_a_total_order(tenant_a, tpl_customer_a2):
    assert LogisticsClient._meta.ordering == ["code", "id"]


def test_3pl_client_ordering_puts_the_codes_in_order(tenant_a):
    _3pl_make_client(tenant_a, "ZULU")
    _3pl_make_client(tenant_a, "ALPHA")
    codes = list(LogisticsClient.objects.filter(tenant=tenant_a).values_list("code", flat=True))
    assert codes == ["ALPHA", "ZULU"]


def test_3pl_client_tenant_scoped_fks_exclude_the_global_currency():
    """``accounting.Currency`` is GLOBAL (no tenant column), so a tenant comparison against it
    would reject every valid selection."""
    assert LogisticsClient.TENANT_SCOPED_FKS == (
        "party", "parent_client", "payment_terms", "default_revenue_account", "contract_document",
        "account_manager")
    assert "currency" not in LogisticsClient.TENANT_SCOPED_FKS


# =================================================================================================
# 4.17 · LogisticsClient — the closed vocabularies
# =================================================================================================
def test_3pl_client_status_choices_are_the_five_commercial_states():
    assert _3pl_values(CLIENT_STATUS_CHOICES) == [
        "prospect", "onboarding", "active", "suspended", "terminated"]
    assert _3pl_values(_3pl_field(LogisticsClient, "status").choices) == _3pl_values(
        CLIENT_STATUS_CHOICES)


def test_3pl_billing_cycle_choices_are_the_four_invoicing_rhythms():
    assert _3pl_values(BILLING_CYCLE_CHOICES) == ["weekly", "biweekly", "monthly", "quarterly"]


def test_3pl_storage_billing_methods_are_the_five_conventions():
    assert _3pl_values(STORAGE_BILLING_METHOD_CHOICES) == [
        "calendar_month", "anniversary", "split_month", "average_daily", "snapshot"]


def test_3pl_space_model_choices_and_the_committed_subset():
    assert _3pl_values(SPACE_MODEL_CHOICES) == ["shared", "dedicated", "hybrid"]
    assert COMMITTED_SPACE_MODELS == ("dedicated", "hybrid")


def test_3pl_integration_modes_are_non_secret_partner_identifiers():
    assert _3pl_values(INTEGRATION_MODE_CHOICES) == [
        "none", "manual", "csv", "api", "edi", "marketplace"]


def test_3pl_no_secret_or_credential_column_lives_on_the_client(tenant_a):
    """L20 — credential storage, EDI transport and webhooks are 4.19's. A secret here would ship
    plaintext in the edit form."""
    names = _3pl_field_names(LogisticsClient)
    forbidden = {"api_key", "api_secret", "token", "password", "secret", "endpoint_url",
                 "webhook_url", "edi_password"}
    assert not (names & forbidden)


def test_3pl_client_status_css_maps_every_status_to_a_real_badge_class():
    assert set(CLIENT_STATUS_CSS) == set(_3pl_values(CLIENT_STATUS_CHOICES))
    assert set(CLIENT_STATUS_CSS.values()) <= _3pl_badge_classes
    assert CLIENT_STATUS_CSS["active"] == "badge-green"
    assert CLIENT_STATUS_CSS["suspended"] == "badge-amber"
    assert CLIENT_STATUS_CSS["terminated"] == "badge-slate"


def test_3pl_client_bounds_match_the_column_shapes():
    assert MAX_COMMITTED_SQFT == Decimal("9999999.99")
    assert MAX_COMMITTED_PALLETS == 1000000
    assert MAX_CLIENT_DEPTH == 10


# =================================================================================================
# 4.17 · LogisticsClient — onboarded_on is stamped ONCE and never restamped
# =================================================================================================
def test_3pl_going_active_stamps_the_onboarding_date(tpl_client_a):
    assert tpl_client_a.onboarded_on == timezone.localdate()


def test_3pl_a_prospect_carries_no_onboarding_date(tenant_a, tpl_customer_a2):
    client = LogisticsClient.objects.create(tenant=tenant_a, party=tpl_customer_a2, code="PROS",
                                            status="prospect")
    assert client.onboarded_on is None


def test_3pl_a_partial_save_that_flips_the_status_still_writes_the_date(tenant_a, tpl_customer_a2):
    """The stamp is a side effect of a save the caller did not ask for, so it has to be added to
    ``update_fields`` or an active client would end up with no onboarding date at all."""
    client = LogisticsClient.objects.create(tenant=tenant_a, party=tpl_customer_a2, code="PART")
    client.status = "active"
    client.save(update_fields=["status"])
    client.refresh_from_db()
    assert client.onboarded_on == timezone.localdate()


def test_3pl_a_suspend_and_reactivate_cycle_does_not_rewrite_the_onboarding_date(tpl_client_a):
    earlier = timezone.localdate() - datetime.timedelta(days=400)
    LogisticsClient.objects.filter(pk=tpl_client_a.pk).update(onboarded_on=earlier)
    tpl_client_a.refresh_from_db()

    tpl_client_a.status = "suspended"
    tpl_client_a.save()
    tpl_client_a.status = "active"
    tpl_client_a.save()

    tpl_client_a.refresh_from_db()
    assert tpl_client_a.onboarded_on == earlier


def test_3pl_the_onboarding_date_is_not_a_form_writable_column():
    assert _3pl_field(LogisticsClient, "onboarded_on").editable is False
    assert _3pl_field(LogisticsClient, "last_synced_at").editable is False


# =================================================================================================
# 4.17 · LogisticsClient.clean() — six guards
# =================================================================================================
def test_3pl_a_party_from_another_workspace_is_refused(tenant_a, customer_b):
    client = LogisticsClient(tenant=tenant_a, party=customer_b, code="XT")
    with pytest.raises(ValidationError) as exc:
        client.full_clean()
    assert "party" in exc.value.message_dict


def test_3pl_a_client_may_not_be_its_own_parent(tpl_client_a):
    tpl_client_a.parent_client = tpl_client_a
    with pytest.raises(ValidationError) as exc:
        tpl_client_a.full_clean()
    assert "parent_client" in exc.value.message_dict


def test_3pl_a_parent_from_another_workspace_is_refused(tpl_client_a, tpl_client_b):
    tpl_client_a.parent_client = tpl_client_b
    with pytest.raises(ValidationError) as exc:
        tpl_client_a.full_clean()
    assert "parent_client" in exc.value.message_dict


def test_3pl_a_cycle_in_the_client_hierarchy_is_refused(tenant_a, tpl_client_a):
    """An unbounded walk against an existing A->B->A cycle is an infinite loop inside form
    validation — a hung request from an ordinary edit."""
    child = _3pl_make_client(tenant_a, "CHILD", parent_client=tpl_client_a)
    tpl_client_a.parent_client = child
    with pytest.raises(ValidationError) as exc:
        tpl_client_a.full_clean()
    assert "loop" in exc.value.message_dict["parent_client"][0].lower()


def test_3pl_a_hierarchy_deeper_than_the_bound_is_refused(tenant_a, tpl_client_a):
    node = None
    for level in range(MAX_CLIENT_DEPTH + 1):
        node = _3pl_make_client(tenant_a, f"L{level:02d}", parent_client=node)
    tpl_client_a.parent_client = node
    with pytest.raises(ValidationError) as exc:
        tpl_client_a.full_clean()
    assert str(MAX_CLIENT_DEPTH) in exc.value.message_dict["parent_client"][0]


def test_3pl_a_shallow_hierarchy_is_accepted(tenant_a, tpl_client_a):
    child = _3pl_make_client(tenant_a, "DIV1")
    child.parent_client = tpl_client_a
    child.full_clean()  # must not raise


@pytest.mark.parametrize("space_model", ["dedicated", "hybrid"])
def test_3pl_a_committed_space_model_with_no_commitment_is_refused(tenant_a, space_model):
    party = _3pl_party(tenant_a, f"No commitment {space_model}")
    client = LogisticsClient(tenant=tenant_a, party=party, code="NOCOM", space_model=space_model)
    with pytest.raises(ValidationError) as exc:
        client.full_clean()
    assert "space_model" in exc.value.message_dict


def test_3pl_a_shared_client_carrying_a_commitment_is_refused(tenant_a):
    """A figure the user typed and the system silently dropped is worse than an error — here it
    would look like rented space nobody agreed to."""
    party = _3pl_party(tenant_a, "Shared with a commitment")
    client = LogisticsClient(tenant=tenant_a, party=party, code="SHCOM", space_model="shared",
                             committed_pallet_positions=100)
    with pytest.raises(ValidationError) as exc:
        client.full_clean()
    assert "space_model" in exc.value.message_dict


def test_3pl_an_over_range_square_footage_is_a_field_error_not_a_data_error(tenant_a):
    party = _3pl_party(tenant_a, "Too much floor")
    client = LogisticsClient(tenant=tenant_a, party=party, code="BIGSQ", space_model="dedicated",
                             committed_sqft=MAX_COMMITTED_SQFT + Decimal("0.01"))
    with pytest.raises(ValidationError) as exc:
        client.full_clean()
    assert "committed_sqft" in exc.value.message_dict


def test_3pl_an_over_range_pallet_commitment_is_a_field_error(tenant_a):
    party = _3pl_party(tenant_a, "Too many pallets")
    client = LogisticsClient(tenant=tenant_a, party=party, code="BIGPP", space_model="dedicated",
                             committed_pallet_positions=MAX_COMMITTED_PALLETS + 1)
    with pytest.raises(ValidationError) as exc:
        client.full_clean()
    assert "committed_pallet_positions" in exc.value.message_dict


def test_3pl_a_contract_that_ends_before_it_starts_is_refused(tpl_client_a):
    tpl_client_a.contract_end = tpl_client_a.contract_start - datetime.timedelta(days=1)
    with pytest.raises(ValidationError) as exc:
        tpl_client_a.full_clean()
    assert "contract_end" in exc.value.message_dict


def test_3pl_a_revenue_account_from_another_workspace_is_refused(tpl_client_a, gl_expense_b):
    tpl_client_a.default_revenue_account = gl_expense_b
    with pytest.raises(ValidationError) as exc:
        tpl_client_a.full_clean()
    assert "default_revenue_account" in exc.value.message_dict


def test_3pl_a_billing_day_past_the_28th_is_refused(tpl_client_a):
    """28, not 31: a client billed on the 30th has no billing day in February."""
    tpl_client_a.billing_day = 29
    with pytest.raises(ValidationError) as exc:
        tpl_client_a.full_clean()
    assert "billing_day" in exc.value.message_dict


def test_3pl_the_fixture_client_validates_as_shipped(tpl_client_a):
    tpl_client_a.full_clean()  # must not raise


# =================================================================================================
# 4.17 · LogisticsClient — every stock figure is DERIVED, never a column (L29 / L37)
# =================================================================================================
@pytest.mark.parametrize("name", ["on_hand_quantity", "on_hand_value", "sku_count",
                                  "dedicated_location_count", "open_sla_breaches",
                                  "last_billing_run"])
def test_3pl_client_stock_figures_are_methods_and_not_stored_columns(name):
    assert name not in _3pl_field_names(LogisticsClient)
    assert callable(getattr(LogisticsClient, name))


def test_3pl_on_hand_quantity_is_the_signed_sum_of_the_ledger(tpl_client_a, tpl_stock_move_a):
    assert tpl_client_a.on_hand_quantity() == Decimal("100")


def test_3pl_on_hand_quantity_moves_with_the_ledger_rather_than_being_stored(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_stock_move_a,
        tpl_period):
    start, _end = tpl_period
    _3pl_stock_move(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, "-30",
                    _3pl_moment(start + datetime.timedelta(days=6)), move_type="issue")
    assert tpl_client_a.on_hand_quantity() == Decimal("70")


def test_3pl_on_hand_value_is_quantity_times_the_cached_average_cost(tpl_client_a,
                                                                     tpl_stock_move_a):
    assert tpl_client_a.on_hand_value() == Decimal("1000.00")


def test_3pl_on_hand_value_skips_an_item_that_nets_to_zero_or_below(
        tenant_a, tpl_client_a, tpl_stock_move_a, tpl_dedicated_location_a, category_a,
        uom_each_a, tpl_period):
    """A net-negative row is a data anomaly rather than negative value held — folding it in would
    understate the position without saying so."""
    from apps.scm.models import Item
    strange = Item.objects.create(
        tenant=tenant_a, sku="3PL-SKU-2", name="Anomalous", category=category_a, uom=uom_each_a,
        item_type="stock", average_cost=Decimal("5.0000"), owner_client=tpl_client_a)
    start, _end = tpl_period
    _3pl_stock_move(tenant_a, strange, tpl_dedicated_location_a, "-10",
                    _3pl_moment(start + datetime.timedelta(days=7)), move_type="adjustment")

    assert tpl_client_a.on_hand_quantity() == Decimal("90")
    assert tpl_client_a.on_hand_value() == Decimal("1000.00")


def test_3pl_on_hand_figures_are_zero_for_an_unsaved_client():
    client = LogisticsClient(code="GHOST")
    assert client.on_hand_quantity() == Decimal("0")
    assert client.on_hand_value() == Decimal("0")
    assert client.sku_count() == 0
    assert client.dedicated_location_count() == 0
    assert client.open_sla_breaches() == 0
    assert client.last_billing_run() is None


def test_3pl_sku_count_counts_assigned_items_not_items_holding_stock(tpl_client_a,
                                                                     tpl_owned_item_a):
    """A client with forty SKUs and an empty warehouse still has forty SKUs."""
    assert tpl_client_a.sku_count() == 1


def test_3pl_dedicated_location_count_counts_reserved_bins(tpl_client_a, tpl_dedicated_location_a,
                                                            tpl_other_client_location_a):
    assert tpl_client_a.dedicated_location_count() == 1


def test_3pl_open_sla_breaches_counts_only_active_breaching_promises(tpl_client_a, tpl_sla_a):
    assert tpl_client_a.open_sla_breaches() == 0
    ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(status="breached")
    assert tpl_client_a.open_sla_breaches() == 1
    ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(is_active=False)
    assert tpl_client_a.open_sla_breaches() == 0


def test_3pl_last_billing_run_is_the_latest_period_not_the_newest_row(
        tenant_a, tpl_client_a, tpl_active_card_a, tpl_billing_run_a, tpl_period):
    """Runs are routinely raised out of order (a late correction for March raised in May)."""
    start, end = tpl_period
    older = ClientBillingRun.objects.create(
        tenant=tenant_a, client=tpl_client_a, rate_card=tpl_active_card_a,
        period_start=start - datetime.timedelta(days=60),
        period_end=end - datetime.timedelta(days=60))
    assert tpl_client_a.last_billing_run() == tpl_billing_run_a
    assert older.period_end < tpl_billing_run_a.period_end


# =================================================================================================
# 4.17 · ClientRateCard — defaults, vocabulary and the derived reads
# =================================================================================================
def test_3pl_rate_card_defaults(tenant_a, tpl_client_a):
    card = ClientRateCard.objects.create(tenant=tenant_a, client=tpl_client_a, name="Bare tariff",
                                         effective_from=timezone.localdate())
    card.refresh_from_db()
    assert card.version == 1
    assert card.status == "draft"
    assert card.effective_to is None
    assert card.currency_id is None
    assert card.notes == ""


def test_3pl_rate_card_status_choices_keep_superseded_and_expired_apart():
    assert _3pl_values(RATE_CARD_STATUS_CHOICES) == ["draft", "active", "superseded", "expired"]
    assert ClientRateCard.STATUS_CHOICES == RATE_CARD_STATUS_CHOICES


def test_3pl_only_a_draft_rate_card_is_editable():
    assert EDITABLE_RATE_CARD_STATUSES == ("draft",)
    assert ClientRateCard.EDITABLE_STATUSES == ("draft",)


def test_3pl_rate_card_status_css_only_uses_real_badge_classes():
    assert set(RATE_CARD_STATUS_CSS) == set(_3pl_values(RATE_CARD_STATUS_CHOICES))
    assert set(RATE_CARD_STATUS_CSS.values()) <= _3pl_badge_classes
    assert RATE_CARD_STATUS_CSS["active"] == "badge-green"


def test_3pl_rate_card_status_css_property_falls_back_to_muted(tpl_rate_card_a):
    assert tpl_rate_card_a.status_css == "badge-muted"
    tpl_rate_card_a.status = "not-a-status"
    assert tpl_rate_card_a.status_css == "badge-muted"


def test_3pl_rate_card_is_editable_tracks_the_status(tpl_rate_card_a, tpl_active_card_a):
    assert tpl_rate_card_a.is_editable is True
    assert tpl_active_card_a.is_editable is False


def test_3pl_rate_card_ordering_is_newest_first():
    assert ClientRateCard._meta.ordering == ["-effective_from", "-version", "-id"]


def test_3pl_active_line_count_is_a_query_and_not_a_column(tpl_active_card_a):
    assert "active_line_count" not in _3pl_field_names(ClientRateCard)
    assert "line_count" not in _3pl_field_names(ClientRateCard)
    assert tpl_active_card_a.active_line_count == 2
    tpl_active_card_a.lines.update(is_active=False)
    assert tpl_active_card_a.active_line_count == 0


def test_3pl_is_effective_on_treats_a_blank_end_date_as_open_ended(tpl_rate_card_a):
    today = timezone.localdate()
    assert tpl_rate_card_a.effective_to is None
    assert tpl_rate_card_a.is_effective_on(today) is False           # starts tomorrow
    assert tpl_rate_card_a.is_effective_on(today + datetime.timedelta(days=1)) is True
    assert tpl_rate_card_a.is_effective_on(today + datetime.timedelta(days=3650)) is True


def test_3pl_is_effective_on_defaults_to_today(tpl_active_card_a):
    assert tpl_active_card_a.is_effective_on() is True


def test_3pl_is_effective_on_says_nothing_about_the_status(tpl_active_card_a):
    """"Is this range live today" and "has anybody activated it" are two different questions."""
    tpl_active_card_a.status = "draft"
    assert tpl_active_card_a.is_effective_on() is True


def test_3pl_is_effective_on_is_false_without_a_start_date():
    assert ClientRateCard(effective_from=None).is_effective_on(timezone.localdate()) is False


# =================================================================================================
# 4.17 · ClientRateCard — the overlap guard, the one implementation behind three callers
# =================================================================================================
def test_3pl_the_shipped_fixtures_do_not_overlap(tpl_active_card_a, tpl_rate_card_a):
    assert tpl_rate_card_a.overlapping_active_card() is None


def test_3pl_an_overlapping_active_card_is_found(tpl_active_card_a, tpl_rate_card_a):
    tpl_rate_card_a.effective_from = timezone.localdate()
    assert tpl_rate_card_a.overlapping_active_card() == tpl_active_card_a


def test_3pl_an_open_ended_active_card_overlaps_everything_after_it(tpl_active_card_a,
                                                                     tpl_rate_card_a):
    ClientRateCard.objects.filter(pk=tpl_active_card_a.pk).update(effective_to=None)
    assert tpl_rate_card_a.overlapping_active_card() is not None


def test_3pl_the_overlap_guard_excludes_the_card_itself(tpl_active_card_a):
    assert tpl_active_card_a.overlapping_active_card() is None


def test_3pl_the_overlap_guard_ignores_another_clients_card(tenant_a, tpl_active_card_a,
                                                             tpl_client_shared_a):
    today = timezone.localdate()
    other = ClientRateCard(tenant=tenant_a, client=tpl_client_shared_a, name="Shared tariff",
                           status="active", effective_from=today - datetime.timedelta(days=10),
                           effective_to=today)
    assert other.overlapping_active_card() is None


def test_3pl_the_overlap_guard_ignores_a_draft_neighbour(tenant_a, tpl_client_shared_a):
    """Several drafts may sit side by side while prices are being negotiated — only an ACTIVE card
    can collide, because only an active card prices anything."""
    today = timezone.localdate()
    ClientRateCard.objects.create(tenant=tenant_a, client=tpl_client_shared_a,
                                  name="Draft neighbour", status="draft",
                                  effective_from=today - datetime.timedelta(days=30),
                                  effective_to=today + datetime.timedelta(days=30))
    candidate = ClientRateCard(tenant=tenant_a, client=tpl_client_shared_a, name="Candidate",
                               status="active", effective_from=today, effective_to=today)
    assert candidate.overlapping_active_card() is None


# =================================================================================================
# 4.17 · ClientRateCard.clean()
# =================================================================================================
def test_3pl_a_tariff_that_stops_before_it_starts_is_refused(tpl_rate_card_a):
    tpl_rate_card_a.effective_to = tpl_rate_card_a.effective_from - datetime.timedelta(days=1)
    with pytest.raises(ValidationError) as exc:
        tpl_rate_card_a.full_clean()
    assert "effective_to" in exc.value.message_dict


def test_3pl_a_tariff_for_another_workspaces_client_is_refused(tenant_a, tpl_client_b):
    card = ClientRateCard(tenant=tenant_a, client=tpl_client_b, name="Crafted",
                          effective_from=timezone.localdate())
    with pytest.raises(ValidationError) as exc:
        card.full_clean()
    assert "client" in exc.value.message_dict


def test_3pl_activating_an_overlapping_tariff_is_refused_on_the_start_date(tpl_active_card_a,
                                                                           tpl_rate_card_a):
    tpl_rate_card_a.status = "active"
    tpl_rate_card_a.effective_from = timezone.localdate()
    with pytest.raises(ValidationError) as exc:
        tpl_rate_card_a.full_clean()
    assert "effective_from" in exc.value.message_dict
    assert tpl_active_card_a.number in exc.value.message_dict["effective_from"][0]


def test_3pl_a_draft_tariff_may_overlap_an_active_one(tpl_active_card_a, tpl_rate_card_a):
    tpl_rate_card_a.effective_from = timezone.localdate()
    tpl_rate_card_a.full_clean()  # draft — must not raise


# =================================================================================================
# 4.17 · ClientRateCardLine — the tenant-LESS child and its rating vocabulary
# =================================================================================================
def test_3pl_rate_card_line_has_no_tenant_column(tpl_rate_card_line_a):
    """A pure child reached through ``rate_card__tenant``; a second tenant FK would be a second
    answer to "whose row is this"."""
    assert "tenant" not in _3pl_field_names(ClientRateCardLine)
    assert tpl_rate_card_line_a.rate_card.tenant_id is not None


def test_3pl_rate_card_line_defaults(tpl_rate_card_a):
    line = ClientRateCardLine.objects.create(
        rate_card=tpl_rate_card_a, charge_category="outbound", charge_basis="per_order",
        description="Order handling")
    line.refresh_from_db()
    assert line.rate == Decimal("0")
    assert line.period == ""
    assert line.included_quantity == Decimal("0")
    assert line.minimum_charge == Decimal("0")
    assert line.tier_from == Decimal("0")
    assert line.tier_to is None
    assert line.applies_to_location_id is None
    assert line.applies_to_item_category_id is None
    assert line.gl_account_id is None
    assert line.is_active is True


def test_3pl_charge_category_choices_are_the_eight_billing_conversations():
    assert _3pl_values(CHARGE_CATEGORY_CHOICES) == [
        "storage", "receiving", "outbound", "value_added", "accessorial", "transportation",
        "recurring", "minimum"]


def test_3pl_charge_basis_choices_are_the_closed_fourteen():
    assert _3pl_values(CHARGE_BASIS_CHOICES) == [
        "per_pallet_position", "per_sqft", "per_cbm", "per_unit", "per_order", "per_line",
        "per_receipt", "per_carton", "per_shipment", "per_kg", "per_hour", "flat_recurring",
        "dedicated_space", "pct_of_value"]


def test_3pl_rate_period_choices_are_day_week_month():
    assert _3pl_values(RATE_PERIOD_CHOICES) == ["day", "week", "month"]


def test_3pl_periodic_and_manual_only_bases_are_subsets_of_the_registry():
    every_basis = set(_3pl_values(CHARGE_BASIS_CHOICES))
    assert set(PERIODIC_BASES) <= every_basis
    assert set(MANUAL_ONLY_BASES) <= every_basis
    assert PERIODIC_BASES == ("per_pallet_position", "per_sqft", "per_cbm", "flat_recurring",
                              "dedicated_space")
    assert MANUAL_ONLY_BASES == ("per_sqft", "per_cbm", "per_kg", "per_hour", "per_carton",
                                 "pct_of_value")


def test_3pl_charge_category_css_only_uses_real_badge_classes():
    assert set(CHARGE_CATEGORY_CSS) == set(_3pl_values(CHARGE_CATEGORY_CHOICES))
    assert set(CHARGE_CATEGORY_CSS.values()) <= _3pl_badge_classes
    assert CHARGE_CATEGORY_CSS["minimum"] == "badge-red"


def test_3pl_category_css_property_falls_back_to_muted(tpl_rate_card_line_a):
    assert tpl_rate_card_line_a.category_css == "badge-green"
    tpl_rate_card_line_a.charge_category = "nonsense"
    assert tpl_rate_card_line_a.category_css == "badge-muted"


@pytest.mark.parametrize("basis", MANUAL_ONLY_BASES)
def test_3pl_an_unmeasurable_basis_reports_that_it_needs_a_quantity(basis):
    assert ClientRateCardLine(charge_basis=basis).needs_manual_quantity is True


def test_3pl_a_measurable_basis_does_not_need_a_manual_quantity(tpl_rate_card_line_a):
    assert tpl_rate_card_line_a.needs_manual_quantity is False


def test_3pl_rate_card_line_ordering_reads_like_the_bill():
    assert ClientRateCardLine._meta.ordering == ["charge_category", "charge_basis", "tier_from",
                                                 "id"]


def test_3pl_tier_bands_are_half_open_so_they_tile_without_double_counting():
    lower = ClientRateCardLine(tier_from=Decimal("0"), tier_to=Decimal("100"))
    upper = ClientRateCardLine(tier_from=Decimal("100"), tier_to=Decimal("500"))
    assert lower.applies_to_quantity(Decimal("0")) is True
    assert lower.applies_to_quantity(Decimal("99.9999")) is True
    assert lower.applies_to_quantity(Decimal("100")) is False
    assert upper.applies_to_quantity(Decimal("100")) is True
    assert upper.applies_to_quantity(Decimal("500")) is False


def test_3pl_an_open_ended_top_band_has_no_upper_bound():
    top = ClientRateCardLine(tier_from=Decimal("500"), tier_to=None)
    assert top.applies_to_quantity(Decimal("500")) is True
    assert top.applies_to_quantity(Decimal("999999")) is True
    assert top.applies_to_quantity(Decimal("499")) is False
    assert top.applies_to_quantity(None) is False


# =================================================================================================
# 4.17 · ClientRateCardLine.clean() — five guards plus the cap
# =================================================================================================
def test_3pl_an_inverted_tier_band_is_refused(tpl_rate_card_a):
    line = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="storage",
                              charge_basis="per_unit", description="Bad band",
                              tier_from=Decimal("100"), tier_to=Decimal("100"))
    with pytest.raises(ValidationError) as exc:
        line.full_clean()
    assert "tier_to" in exc.value.message_dict


def test_3pl_a_period_on_an_event_basis_is_refused(tpl_rate_card_a):
    line = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="outbound",
                              charge_basis="per_order", description="Order fee", period="month")
    with pytest.raises(ValidationError) as exc:
        line.full_clean()
    assert "period" in exc.value.message_dict


@pytest.mark.parametrize("basis", PERIODIC_BASES)
def test_3pl_a_periodic_basis_without_a_period_is_refused(tpl_rate_card_a, basis):
    """A "£3.50 per pallet position" with no period is not a price — per day and per month differ
    by a factor of thirty."""
    line = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="storage",
                              charge_basis=basis, description="Periodic", period="")
    with pytest.raises(ValidationError) as exc:
        line.full_clean()
    assert "period" in exc.value.message_dict


def test_3pl_a_line_scoped_to_another_clients_location_is_refused(tpl_rate_card_a,
                                                                   tpl_other_client_location_a):
    line = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="storage",
                              charge_basis="per_unit", description="Someone else's aisle",
                              applies_to_location=tpl_other_client_location_a)
    with pytest.raises(ValidationError) as exc:
        line.full_clean()
    assert "applies_to_location" in exc.value.message_dict


def test_3pl_a_line_scoped_to_this_clients_own_location_is_accepted(tpl_rate_card_a,
                                                                     tpl_dedicated_location_a):
    line = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="storage",
                              charge_basis="per_unit", description="Own aisle",
                              applies_to_location=tpl_dedicated_location_a)
    line.full_clean()  # must not raise


def test_3pl_a_line_scoped_to_another_workspaces_location_is_refused(tpl_rate_card_a, location_b):
    line = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="storage",
                              charge_basis="per_unit", description="Foreign aisle",
                              applies_to_location=location_b)
    with pytest.raises(ValidationError) as exc:
        line.full_clean()
    assert "applies_to_location" in exc.value.message_dict


def test_3pl_a_line_scoped_to_another_workspaces_item_category_is_refused(tpl_rate_card_a,
                                                                          category_b):
    line = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="storage",
                              charge_basis="per_unit", description="Foreign category",
                              applies_to_item_category=category_b)
    with pytest.raises(ValidationError) as exc:
        line.full_clean()
    assert "applies_to_item_category" in exc.value.message_dict


def test_3pl_a_line_posting_to_another_workspaces_gl_account_is_refused(tpl_rate_card_a,
                                                                        gl_expense_b):
    line = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="storage",
                              charge_basis="per_unit", description="Foreign account",
                              gl_account=gl_expense_b)
    with pytest.raises(ValidationError) as exc:
        line.full_clean()
    assert "gl_account" in exc.value.message_dict


def test_3pl_dedicated_space_cannot_be_billed_to_a_shared_client(tenant_a, tpl_client_shared_a):
    card = ClientRateCard.objects.create(tenant=tenant_a, client=tpl_client_shared_a,
                                         name="Shared tariff",
                                         effective_from=timezone.localdate())
    line = ClientRateCardLine(rate_card=card, charge_category="storage",
                              charge_basis="dedicated_space", description="Space nobody rented",
                              period="month")
    with pytest.raises(ValidationError) as exc:
        line.full_clean()
    assert "charge_basis" in exc.value.message_dict


def test_3pl_dedicated_space_is_accepted_on_a_dedicated_client(tpl_rate_card_a):
    line = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="storage",
                              charge_basis="dedicated_space", description="Committed space",
                              period="month")
    line.full_clean()  # must not raise


def test_3pl_a_tariff_may_not_grow_past_the_line_cap(tpl_rate_card_a):
    assert MAX_RATE_CARD_LINES == 200
    ClientRateCardLine.objects.bulk_create([
        ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="accessorial",
                           charge_basis="per_order", description=f"Filler {index}")
        for index in range(MAX_RATE_CARD_LINES)
    ])
    extra = ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="accessorial",
                               charge_basis="per_order", description="One too many")
    with pytest.raises(ValidationError) as exc:
        extra.full_clean()
    assert NON_FIELD_ERRORS in exc.value.message_dict


def test_3pl_the_line_cap_does_not_strand_an_existing_row(tpl_rate_card_a, tpl_rate_card_line_a):
    """Bounded on the CREATE path only — refusing to save an existing row would strand a card that
    somehow exceeded the cap."""
    ClientRateCardLine.objects.bulk_create([
        ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="accessorial",
                           charge_basis="per_order", description=f"Filler {index}")
        for index in range(MAX_RATE_CARD_LINES)
    ])
    tpl_rate_card_line_a.rate = Decimal("13.0000")
    tpl_rate_card_line_a.full_clean()  # must not raise


# =================================================================================================
# 4.17 · ClientBillingRun — defaults, the ladder vocabulary and the derived money columns
# =================================================================================================
def test_3pl_billing_run_defaults(tpl_billing_run_a):
    tpl_billing_run_a.refresh_from_db()
    assert tpl_billing_run_a.status == "draft"
    assert tpl_billing_run_a.subtotal == Decimal("0.00")
    assert tpl_billing_run_a.minimum_adjustment == Decimal("0.00")
    assert tpl_billing_run_a.total == Decimal("0.00")
    assert tpl_billing_run_a.calculated_at is None
    assert tpl_billing_run_a.approved_at is None
    assert tpl_billing_run_a.approved_by_id is None
    assert tpl_billing_run_a.invoice_id is None


def test_3pl_run_status_choices_are_the_ladder():
    assert _3pl_values(RUN_STATUS_CHOICES) == ["draft", "calculated", "approved", "invoiced",
                                               "void"]
    assert EDITABLE_RUN_STATUSES == ("draft", "calculated")
    assert ClientBillingRun.EDITABLE_STATUSES == ("draft", "calculated")
    assert ClientBillingRun.VOIDABLE_STATUSES == ("draft", "calculated")


def test_3pl_run_status_css_only_uses_real_badge_classes():
    assert set(RUN_STATUS_CSS) == set(_3pl_values(RUN_STATUS_CHOICES))
    assert set(RUN_STATUS_CSS.values()) <= _3pl_badge_classes
    assert RUN_STATUS_CSS["invoiced"] == "badge-green"


@pytest.mark.parametrize("name", ["status", "subtotal", "minimum_adjustment", "total",
                                  "calculated_at", "approved_at", "approved_by", "invoice"])
def test_3pl_every_run_workflow_column_is_off_the_forms(name):
    """A status a user can type is a status that can be set to ``invoiced`` on a run that was never
    calculated (L22/L35)."""
    assert _3pl_field(ClientBillingRun, name).editable is False


def test_3pl_run_bounds_and_ordering():
    assert ClientBillingRun._meta.ordering == ["-period_end", "-id"]
    assert ClientBillingRun.MINIMUM_CHARGE_MIN_DAYS == 28
    assert MAX_RUN_LINES == 500
    assert MAX_RUN_PERIOD_DAYS == 366
    assert MAX_MEASUREMENT_ROWS == 20000


def test_3pl_period_days_is_inclusive(tpl_billing_run_a, tpl_period):
    start, end = tpl_period
    assert tpl_billing_run_a.period_days == (end - start).days + 1


def test_3pl_period_days_is_zero_on_an_unbounded_instance():
    assert ClientBillingRun().period_days == 0


def test_3pl_run_is_editable_up_to_approval(tpl_billing_run_a):
    assert tpl_billing_run_a.is_editable is True
    tpl_billing_run_a.status = "approved"
    assert tpl_billing_run_a.is_editable is False


# =================================================================================================
# 4.17 · ClientBillingRun — money is DERIVED, summed in Python, never typed
# =================================================================================================
def test_3pl_recalc_amounts_sums_the_lines(tpl_billing_run_a, tpl_billing_run_line_a):
    total = tpl_billing_run_a.recalc_amounts()
    tpl_billing_run_a.refresh_from_db()
    assert tpl_billing_run_a.subtotal == Decimal("50.00")
    # A monthly client with a 500.00 floor over a full calendar month is topped up.
    assert tpl_billing_run_a.minimum_adjustment == Decimal("450.00")
    assert tpl_billing_run_a.total == total == Decimal("500.00")


def test_3pl_the_monthly_minimum_is_not_applied_to_a_short_period(tenant_a, tpl_client_a,
                                                                   tpl_active_card_a):
    today = timezone.localdate()
    run = ClientBillingRun.objects.create(
        tenant=tenant_a, client=tpl_client_a, rate_card=tpl_active_card_a,
        period_start=today - datetime.timedelta(days=6), period_end=today)
    ClientBillingRunLine.objects.create(run=run, charge_category="outbound",
                                        charge_basis="per_order", description="Handling",
                                        quantity=Decimal("1"), rate=Decimal("10.0000"))
    run.recalc_amounts()
    run.refresh_from_db()
    assert run.period_days == 7
    assert run.minimum_adjustment == Decimal("0.00")
    assert run.total == Decimal("10.00")


def test_3pl_the_monthly_minimum_is_not_applied_to_a_weekly_client(tenant_a, tpl_client_shared_a,
                                                                    tpl_period):
    card = ClientRateCard.objects.create(tenant=tenant_a, client=tpl_client_shared_a,
                                         name="Shared tariff", status="active",
                                         effective_from=tpl_period[0])
    start, end = tpl_period
    run = ClientBillingRun.objects.create(tenant=tenant_a, client=tpl_client_shared_a,
                                          rate_card=card, period_start=start, period_end=end)
    LogisticsClient.objects.filter(pk=tpl_client_shared_a.pk).update(
        minimum_monthly_charge=Decimal("900.00"))
    run.refresh_from_db()
    run.recalc_amounts()
    assert run.minimum_adjustment == Decimal("0.00")
    applied, reason = run.minimum_status()
    assert applied is False
    assert "weekly" in reason


def test_3pl_minimum_status_explains_a_client_with_no_floor(tenant_a, tpl_client_shared_a,
                                                             tpl_period):
    run = ClientBillingRun(tenant=tenant_a, client=tpl_client_shared_a,
                           period_start=tpl_period[0], period_end=tpl_period[1])
    applied, reason = run.minimum_status()
    assert applied is False
    assert "no monthly minimum" in reason


def test_3pl_minimum_status_explains_a_short_period(tenant_a, tpl_client_a):
    today = timezone.localdate()
    run = ClientBillingRun(tenant=tenant_a, client=tpl_client_a,
                           period_start=today - datetime.timedelta(days=3), period_end=today)
    applied, reason = run.minimum_status()
    assert applied is False
    assert str(ClientBillingRun.MINIMUM_CHARGE_MIN_DAYS) in reason


def test_3pl_minimum_status_reports_the_top_up_it_applied(tpl_billing_run_a,
                                                           tpl_billing_run_line_a):
    tpl_billing_run_a.recalc_amounts()
    applied, reason = tpl_billing_run_a.minimum_status()
    assert applied is True
    assert "applied:" in reason


def test_3pl_minimum_status_says_when_the_charges_already_clear_the_floor(tpl_billing_run_a):
    ClientBillingRunLine.objects.create(run=tpl_billing_run_a, charge_category="outbound",
                                        charge_basis="per_order", description="Big month",
                                        quantity=Decimal("1"), rate=Decimal("900.0000"))
    tpl_billing_run_a.recalc_amounts()
    applied, reason = tpl_billing_run_a.minimum_status()
    assert applied is False
    assert "already meet" in reason


# =================================================================================================
# 4.17 · ClientBillingRun.calculate() — the engine
# =================================================================================================
def test_3pl_calculate_prices_the_period_from_the_tariff(tpl_billing_run_a):
    result = tpl_billing_run_a.calculate()
    tpl_billing_run_a.refresh_from_db()
    assert result["lines_written"] == 1
    assert result["manual_lines"] == 0
    assert result["truncated"] is False
    assert tpl_billing_run_a.status == "calculated"
    assert tpl_billing_run_a.calculated_at is not None
    assert tpl_billing_run_a.subtotal == Decimal("250.00")
    assert tpl_billing_run_a.minimum_adjustment == Decimal("250.00")
    assert tpl_billing_run_a.total == Decimal("500.00")


def test_3pl_calculate_writes_the_evidence_onto_every_derived_line(tpl_billing_run_a):
    tpl_billing_run_a.calculate()
    line = tpl_billing_run_a.lines.get()
    assert line.is_manual is False
    assert line.rate_card_line_id is not None
    assert line.charge_basis == "flat_recurring"
    assert line.quantity == Decimal("1.0000")
    assert line.rate == Decimal("250.0000")
    assert line.amount == Decimal("250.00")
    assert line.source_reference


def test_3pl_calculate_keeps_a_manual_line_and_replaces_only_the_derived_ones(
        tpl_billing_run_a, tpl_billing_run_line_a):
    first = tpl_billing_run_a.calculate()
    assert first["manual_lines"] == 1
    derived_pk = tpl_billing_run_a.lines.filter(is_manual=False).get().pk

    second = tpl_billing_run_a.calculate()
    tpl_billing_run_a.refresh_from_db()
    assert second["lines_written"] == 1
    assert tpl_billing_run_a.lines.filter(is_manual=True).get().pk == tpl_billing_run_line_a.pk
    assert tpl_billing_run_a.lines.filter(is_manual=False).get().pk != derived_pk
    assert tpl_billing_run_a.subtotal == Decimal("300.00")
    assert tpl_billing_run_a.minimum_adjustment == Decimal("200.00")
    assert tpl_billing_run_a.total == Decimal("500.00")


def test_3pl_calculate_skips_a_charge_that_measured_nothing(tpl_billing_run_a, tpl_active_card_a):
    """The per_receipt line resolves to 0 with no receipts in the period — the correct answer, and
    not an error."""
    tpl_billing_run_a.calculate()
    assert tpl_active_card_a.lines.count() == 2
    assert tpl_billing_run_a.lines.count() == 1


def test_3pl_calculate_refuses_a_run_that_has_left_the_editable_statuses(tpl_billing_run_a,
                                                                         admin_user):
    tpl_billing_run_a.calculate()
    tpl_billing_run_a.approve(admin_user)
    with pytest.raises(ValidationError):
        tpl_billing_run_a.calculate()


def test_3pl_a_run_line_keeps_its_snapshot_when_the_tariff_line_goes(tpl_billing_run_a,
                                                                      tpl_active_card_a):
    tpl_billing_run_a.calculate()
    line = tpl_billing_run_a.lines.get()
    tpl_active_card_a.lines.filter(charge_basis="flat_recurring").delete()
    line.refresh_from_db()
    assert line.rate_card_line_id is None
    assert line.charge_basis == "flat_recurring"
    assert line.rate == Decimal("250.0000")
    assert line.amount == Decimal("250.00")
    assert line.is_manual is False


# =================================================================================================
# 4.17 · ClientBillingRun — the verb ladder, and every absent prerequisite REFUSED (L35)
# =================================================================================================
def test_3pl_approve_refuses_a_run_that_was_never_calculated(tpl_billing_run_a, admin_user):
    with pytest.raises(ValidationError):
        tpl_billing_run_a.approve(admin_user)
    tpl_billing_run_a.refresh_from_db()
    assert tpl_billing_run_a.status == "draft"


def test_3pl_approve_stamps_the_signature(tpl_billing_run_a, admin_user):
    tpl_billing_run_a.calculate()
    tpl_billing_run_a.approve(admin_user)
    tpl_billing_run_a.refresh_from_db()
    assert tpl_billing_run_a.status == "approved"
    assert tpl_billing_run_a.approved_by_id == admin_user.id
    assert tpl_billing_run_a.approved_at is not None


def test_3pl_draft_invoice_refuses_a_run_that_was_never_approved(tpl_billing_run_a, admin_user):
    tpl_billing_run_a.calculate()
    with pytest.raises(ValidationError):
        tpl_billing_run_a.draft_invoice(admin_user)
    tpl_billing_run_a.refresh_from_db()
    assert tpl_billing_run_a.status == "calculated"
    assert tpl_billing_run_a.invoice_id is None


def test_3pl_draft_invoice_creates_a_draft_whose_subtotal_equals_the_run(tpl_billing_run_a,
                                                                         admin_user):
    tpl_billing_run_a.calculate()
    tpl_billing_run_a.approve(admin_user)
    invoice = tpl_billing_run_a.draft_invoice(admin_user)
    tpl_billing_run_a.refresh_from_db()

    assert invoice.status == "draft"
    assert invoice.kind == "invoice"
    assert invoice.party_id == tpl_billing_run_a.client.party_id
    assert invoice.issue_date == timezone.localdate()
    assert invoice.subtotal == tpl_billing_run_a.total
    assert tpl_billing_run_a.status == "invoiced"
    assert tpl_billing_run_a.invoice_id == invoice.id


def test_3pl_every_drafted_invoice_line_carries_the_amount_as_its_unit_price(tpl_billing_run_a,
                                                                              admin_user):
    """``accounting.InvoiceLine.unit_price`` is (14,2) and its save() recomputes the line total, so
    a 4dp storage rate written there would silently re-round the invoice away from the run."""
    tpl_billing_run_a.calculate()
    tpl_billing_run_a.approve(admin_user)
    invoice = tpl_billing_run_a.draft_invoice(admin_user)

    lines = list(invoice.lines.all())
    assert len(lines) == 2  # the derived charge + the monthly minimum top-up
    assert all(line.quantity == Decimal("1") for line in lines)
    assert sorted(line.unit_price for line in lines) == [Decimal("250.00"), Decimal("250.00")]
    assert any("Monthly minimum top-up" in line.description for line in lines)


def test_3pl_drafting_an_invoice_posts_no_journal_entry(tpl_billing_run_a, admin_user):
    """L29 — SCM's furthest reach into money is a DRAFT invoice; the ledger is Module 2's."""
    from apps.accounting.models import JournalEntry
    before = JournalEntry.objects.count()
    tpl_billing_run_a.calculate()
    tpl_billing_run_a.approve(admin_user)
    tpl_billing_run_a.draft_invoice(admin_user)
    assert JournalEntry.objects.count() == before


def test_3pl_a_run_cannot_be_invoiced_twice(tpl_billing_run_a, admin_user):
    tpl_billing_run_a.calculate()
    tpl_billing_run_a.approve(admin_user)
    first = tpl_billing_run_a.draft_invoice(admin_user)
    with pytest.raises(ValidationError):
        tpl_billing_run_a.draft_invoice(admin_user)
    tpl_billing_run_a.refresh_from_db()
    assert tpl_billing_run_a.invoice_id == first.id


def test_3pl_void_takes_a_draft_run_off_the_board(tpl_billing_run_a, admin_user):
    tpl_billing_run_a.void(admin_user)
    tpl_billing_run_a.refresh_from_db()
    assert tpl_billing_run_a.status == "void"


def test_3pl_void_refuses_an_invoiced_run(tpl_billing_run_a, admin_user):
    tpl_billing_run_a.calculate()
    tpl_billing_run_a.approve(admin_user)
    tpl_billing_run_a.draft_invoice(admin_user)
    with pytest.raises(ValidationError):
        tpl_billing_run_a.void(admin_user)
    tpl_billing_run_a.refresh_from_db()
    assert tpl_billing_run_a.status == "invoiced"


def test_3pl_void_refuses_an_approved_run(tpl_billing_run_a, admin_user):
    tpl_billing_run_a.calculate()
    tpl_billing_run_a.approve(admin_user)
    with pytest.raises(ValidationError):
        tpl_billing_run_a.void(admin_user)
    tpl_billing_run_a.refresh_from_db()
    assert tpl_billing_run_a.status == "approved"


# =================================================================================================
# 4.17 · the quantity resolvers — the five storage conventions produce five different figures from
# ONE ledger, which is why `storage_billing_method` is the most consequential setting on a client
# =================================================================================================
def _3pl_storage_line(card, basis="per_pallet_position", period="month", rate="1.0000"):
    """A storage charge on ``card``. Written with ``objects.create`` so the fixture card's status
    does not have to be walked back to draft just to price a period."""
    return ClientRateCardLine.objects.create(
        rate_card=card, charge_category="storage", charge_basis=basis,
        description="Pallet storage", rate=Decimal(rate), period=period)


def _3pl_seed_storage_ledger(tenant, item, location, period):
    """+40 BEFORE the period, +100 on day 5 and +60 on day 20 inside it.

    Chosen so the five conventions are all distinguishable and all deterministic in every month:
    a snapshot sees 200, a calendar-month opening balance sees 40, split-month halves only the
    day-20 receipt (170) and the average lands strictly between the opening and closing balance.
    """
    start, _end = period
    _3pl_stock_move(tenant, item, location, "40", _3pl_moment(start - datetime.timedelta(days=10)))
    _3pl_stock_move(tenant, item, location, "100", _3pl_moment(start + datetime.timedelta(days=4)))
    _3pl_stock_move(tenant, item, location, "60", _3pl_moment(start + datetime.timedelta(days=19)))


def _3pl_storage_quantity(run, method):
    """Re-price ``run`` under ``method`` and return the storage line's derived quantity."""
    LogisticsClient.objects.filter(pk=run.client_id).update(storage_billing_method=method)
    run.refresh_from_db()
    run.calculate()
    return run.lines.get(charge_basis="per_pallet_position").quantity


@pytest.mark.parametrize("method, expected", [
    ("snapshot", Decimal("200.0000")),        # the balance at the end of the period
    ("calendar_month", Decimal("40.0000")),   # the balance at the start of it
    ("split_month", Decimal("170.0000")),     # opening + day-5 in full + day-20 at half weight
    ("anniversary", Decimal("200.0000")),     # each receipt's anniversaries inside the period
])
def test_3pl_each_storage_convention_reads_the_same_ledger_differently(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_active_card_a,
        tpl_billing_run_a, tpl_period, method, expected):
    _3pl_seed_storage_ledger(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_period)
    _3pl_storage_line(tpl_active_card_a)
    assert _3pl_storage_quantity(tpl_billing_run_a, method) == expected


def test_3pl_average_daily_storage_lands_between_the_opening_and_closing_balance(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_active_card_a,
        tpl_billing_run_a, tpl_period):
    """Walked day by day in Python — the exact mean depends on the month's length, but it can never
    sit outside the two balances it is a mean of."""
    _3pl_seed_storage_ledger(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_period)
    _3pl_storage_line(tpl_active_card_a)
    average = _3pl_storage_quantity(tpl_billing_run_a, "average_daily")
    assert Decimal("40") < average < Decimal("200")


def test_3pl_a_storage_line_says_which_ledger_and_approximation_it_used(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_active_card_a,
        tpl_billing_run_a, tpl_period):
    """One stock unit billed as one pallet position is a STATED approximation — an invented
    units-per-pallet factor would silently divide every storage bill."""
    _3pl_seed_storage_ledger(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_period)
    _3pl_storage_line(tpl_active_card_a)
    tpl_billing_run_a.calculate()
    line = tpl_billing_run_a.lines.get(charge_basis="per_pallet_position")
    assert "StockMove ledger" in line.source_reference
    assert "1 stock unit billed as 1 pallet position" in line.description


def test_3pl_a_storage_line_narrowed_to_a_location_prices_only_that_bin(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, location_a,
        tpl_active_card_a, tpl_billing_run_a, tpl_period):
    start, _end = tpl_period
    _3pl_stock_move(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, "100",
                    _3pl_moment(start + datetime.timedelta(days=4)))
    _3pl_stock_move(tenant_a, tpl_owned_item_a, location_a, "70",
                    _3pl_moment(start + datetime.timedelta(days=5)))
    line = _3pl_storage_line(tpl_active_card_a)
    line.applies_to_location = tpl_dedicated_location_a
    line.save()

    assert _3pl_storage_quantity(tpl_billing_run_a, "snapshot") == Decimal("100.0000")


@pytest.mark.parametrize("period, expected_weeks", [("day", None), ("week", None)])
def test_3pl_a_recurring_charge_counts_whole_periods(tpl_active_card_a, tpl_billing_run_a,
                                                      period, expected_weeks):
    """A week is exactly 7 days; a MONTH is the summed fraction of each calendar month the period
    touches, never an invented 30-day constant."""
    tpl_active_card_a.lines.filter(charge_basis="flat_recurring").update(period=period)
    tpl_billing_run_a.calculate()
    line = tpl_billing_run_a.lines.get(charge_basis="flat_recurring")
    days = Decimal(tpl_billing_run_a.period_days)
    assert line.quantity == (days if period == "day" else (days / 7).quantize(Decimal("0.0001")))


def test_3pl_a_full_calendar_month_is_exactly_one_month(tpl_billing_run_a):
    tpl_billing_run_a.calculate()
    assert tpl_billing_run_a.lines.get(charge_basis="flat_recurring").quantity == Decimal("1.0000")


def test_3pl_dedicated_space_bills_the_contracted_commitment(tpl_active_card_a,
                                                              tpl_billing_run_a, tpl_client_a):
    _3pl_storage_line(tpl_active_card_a, basis="dedicated_space")
    tpl_billing_run_a.calculate()
    line = tpl_billing_run_a.lines.get(charge_basis="dedicated_space")
    assert line.quantity == Decimal("250.0000")
    assert "committed pallet positions" in line.source_reference


def test_3pl_a_hybrid_client_is_billed_the_greater_of_commitment_and_occupancy(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_active_card_a,
        tpl_billing_run_a, tpl_period):
    start, _end = tpl_period
    _3pl_stock_move(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, "400",
                    _3pl_moment(start + datetime.timedelta(days=2)))
    LogisticsClient.objects.filter(pk=tpl_client_a.pk).update(space_model="hybrid",
                                                              storage_billing_method="snapshot")
    _3pl_storage_line(tpl_active_card_a, basis="dedicated_space")
    tpl_billing_run_a.refresh_from_db()
    tpl_billing_run_a.calculate()

    line = tpl_billing_run_a.lines.get(charge_basis="dedicated_space")
    assert line.quantity == Decimal("400.0000")
    assert "hybrid space" in line.description


@pytest.mark.parametrize("basis", MANUAL_ONLY_BASES)
def test_3pl_an_unmeasurable_charge_is_written_with_a_zero_and_the_missing_measurement_named(
        tpl_active_card_a, tpl_billing_run_a, basis):
    """A guessed conversion factor is a number a client would be invoiced on and nobody could
    defend; a zero with a visible "needs a quantity" chip is a number somebody fixes."""
    period = "month" if basis in PERIODIC_BASES else ""
    ClientRateCardLine.objects.create(
        rate_card=tpl_active_card_a, charge_category="value_added", charge_basis=basis,
        description="Unmeasurable charge", rate=Decimal("3.0000"), period=period)
    tpl_billing_run_a.calculate()

    line = tpl_billing_run_a.lines.get(charge_basis=basis)
    assert line.quantity == Decimal("0.0000")
    assert line.needs_manual_quantity is True
    assert line.is_manual is False
    assert "needs a manual quantity" in line.description
    assert line.amount == Decimal("0.00")


def test_3pl_an_included_allowance_is_netted_off_and_said_on_the_line(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_active_card_a,
        tpl_billing_run_a, tpl_period):
    _3pl_seed_storage_ledger(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_period)
    line = _3pl_storage_line(tpl_active_card_a)
    line.included_quantity = Decimal("50.0000")
    line.save()

    assert _3pl_storage_quantity(tpl_billing_run_a, "snapshot") == Decimal("150.0000")
    assert "included" in tpl_billing_run_a.lines.get(
        charge_basis="per_pallet_position").description


# =================================================================================================
# 4.17 · ClientBillingRun.clean()
# =================================================================================================
def test_3pl_a_run_for_another_workspaces_client_is_refused(tenant_a, tpl_client_b,
                                                             tpl_rate_card_b, tpl_period):
    run = ClientBillingRun(tenant=tenant_a, client=tpl_client_b, rate_card=tpl_rate_card_b,
                           period_start=tpl_period[0], period_end=tpl_period[1])
    with pytest.raises(ValidationError) as exc:
        run.full_clean()
    assert "client" in exc.value.message_dict
    assert "rate_card" in exc.value.message_dict


def test_3pl_a_period_that_ends_before_it_starts_is_refused(tenant_a, tpl_client_a,
                                                             tpl_active_card_a, tpl_period):
    run = ClientBillingRun(tenant=tenant_a, client=tpl_client_a, rate_card=tpl_active_card_a,
                           period_start=tpl_period[1], period_end=tpl_period[0])
    with pytest.raises(ValidationError) as exc:
        run.full_clean()
    assert "period_end" in exc.value.message_dict


def test_3pl_a_period_longer_than_the_cap_is_refused(tenant_a, tpl_client_a, tpl_active_card_a):
    today = timezone.localdate()
    run = ClientBillingRun(tenant=tenant_a, client=tpl_client_a, rate_card=tpl_active_card_a,
                           period_start=today - datetime.timedelta(days=MAX_RUN_PERIOD_DAYS),
                           period_end=today)
    with pytest.raises(ValidationError) as exc:
        run.full_clean()
    assert str(MAX_RUN_PERIOD_DAYS) in exc.value.message_dict["period_end"][0]


def test_3pl_a_tariff_belonging_to_another_client_is_refused(tenant_a, tpl_client_shared_a,
                                                              tpl_active_card_a, tpl_period):
    """The one mistake in this sub-module that quietly bills the wrong company at somebody else's
    rates, and every figure downstream of it looks perfectly plausible."""
    run = ClientBillingRun(tenant=tenant_a, client=tpl_client_shared_a,
                           rate_card=tpl_active_card_a,
                           period_start=tpl_period[0], period_end=tpl_period[1])
    with pytest.raises(ValidationError) as exc:
        run.full_clean()
    assert "another client" in exc.value.message_dict["rate_card"][0]


def test_3pl_a_tariff_that_does_not_cover_the_period_is_refused(tenant_a, tpl_client_a,
                                                                 tpl_active_card_a):
    today = timezone.localdate()
    run = ClientBillingRun(tenant=tenant_a, client=tpl_client_a, rate_card=tpl_active_card_a,
                           period_start=today + datetime.timedelta(days=10),
                           period_end=today + datetime.timedelta(days=20))
    with pytest.raises(ValidationError) as exc:
        run.full_clean()
    assert "does not overlap" in exc.value.message_dict["rate_card"][0]


def test_3pl_the_fixture_run_validates_as_shipped(tpl_billing_run_a):
    tpl_billing_run_a.full_clean()  # must not raise


# =================================================================================================
# 4.17 · ClientBillingRunLine — the tenant-LESS child whose amount nobody types
# =================================================================================================
def test_3pl_billing_run_line_has_no_tenant_column(tpl_billing_run_line_a):
    assert "tenant" not in _3pl_field_names(ClientBillingRunLine)
    assert tpl_billing_run_line_a.run.tenant_id is not None


def test_3pl_billing_run_line_defaults(tpl_billing_run_a):
    line = ClientBillingRunLine.objects.create(
        run=tpl_billing_run_a, charge_category="storage", charge_basis="per_unit",
        description="Bare line")
    line.refresh_from_db()
    assert line.rate_card_line_id is None
    assert line.quantity == Decimal("0")
    assert line.rate == Decimal("0")
    assert line.amount == Decimal("0.00")
    assert line.source_reference == ""
    assert line.is_manual is False
    assert line.needs_manual_quantity is False


def test_3pl_the_run_line_amount_is_derived_and_off_every_form():
    assert _3pl_field(ClientBillingRunLine, "amount").editable is False
    assert _3pl_field(ClientBillingRunLine, "needs_manual_quantity").editable is False


def test_3pl_the_run_line_amount_is_quantity_times_rate(tpl_billing_run_line_a):
    assert tpl_billing_run_line_a.amount == Decimal("50.00")


def test_3pl_the_run_line_amount_is_recomputed_on_a_partial_save(tpl_billing_run_line_a):
    """``amount`` rides along on any partial save or the row would keep a stale figure while its
    quantity moved."""
    tpl_billing_run_line_a.quantity = Decimal("4.0000")
    tpl_billing_run_line_a.save(update_fields=["quantity"])
    tpl_billing_run_line_a.refresh_from_db()
    assert tpl_billing_run_line_a.amount == Decimal("100.00")


def test_3pl_the_tariff_minimum_is_a_floor_and_not_an_addition(tpl_billing_run_a,
                                                                tpl_rate_card_line_a):
    """A per-order fee with a 250.00 minimum bills 250.00 on a slow month and the real figure on a
    busy one."""
    tpl_rate_card_line_a.minimum_charge = Decimal("250.00")
    tpl_rate_card_line_a.save()

    slow = ClientBillingRunLine.objects.create(
        run=tpl_billing_run_a, rate_card_line=tpl_rate_card_line_a, charge_category="receiving",
        charge_basis="per_receipt", description="Slow month", quantity=Decimal("1"),
        rate=Decimal("12.0000"))
    busy = ClientBillingRunLine.objects.create(
        run=tpl_billing_run_a, rate_card_line=tpl_rate_card_line_a, charge_category="receiving",
        charge_basis="per_receipt", description="Busy month", quantity=Decimal("100"),
        rate=Decimal("12.0000"))

    assert slow.amount == Decimal("250.00")
    assert busy.amount == Decimal("1200.00")


def test_3pl_a_manual_line_is_the_one_with_no_tariff_line_behind_it(tpl_billing_run_line_a):
    assert tpl_billing_run_line_a.rate_card_line_id is None
    assert tpl_billing_run_line_a.is_manual is True


def test_3pl_run_line_ordering_groups_by_charge_category():
    assert ClientBillingRunLine._meta.ordering == ["charge_category", "id"]


# =================================================================================================
# 4.17 · ClientSLA — defaults, the closed registry and the eight evidence columns
# =================================================================================================
def test_3pl_sla_defaults(tenant_a, tpl_client_a):
    sla = ClientSLA.objects.create(tenant=tenant_a, client=tpl_client_a, metric="otif_pct",
                                   target_value=Decimal("95.00"))
    sla.refresh_from_db()
    assert sla.name == ""
    assert sla.unit == "pct"
    assert sla.direction == "higher_is_better"
    assert sla.warning_threshold is None
    assert sla.measurement_window == "monthly"
    assert sla.scope_location_id is None
    assert sla.service_credit_pct == Decimal("0")
    assert sla.service_credit_cap_pct == Decimal("0")
    assert sla.is_active is True
    assert sla.notes == ""


def test_3pl_a_new_sla_has_never_been_measured(tpl_sla_a):
    """NULL means never measured — it must render as "Not measured", never as 0."""
    assert tpl_sla_a.status == "no_data"
    assert tpl_sla_a.last_measured_value is None
    assert tpl_sla_a.last_measured_at is None
    assert tpl_sla_a.measurement_window_start is None
    assert tpl_sla_a.measurement_window_end is None
    assert tpl_sla_a.measurement_summary == ""
    assert tpl_sla_a.sample_size == 0
    assert tpl_sla_a.breach_count == 0
    assert tpl_sla_a.is_measured is False


@pytest.mark.parametrize("name", ["last_measured_value", "last_measured_at",
                                  "measurement_window_start", "measurement_window_end",
                                  "measurement_summary", "sample_size", "breach_count", "status"])
def test_3pl_every_sla_evidence_column_is_off_the_forms(name):
    """A measured figure a user can retype is not a measurement (L22)."""
    assert _3pl_field(ClientSLA, name).editable is False


def test_3pl_is_active_is_a_switch_while_status_is_a_measurement():
    """The two look alike and are opposites — one is the human's, one is the ledger's."""
    assert _3pl_field(ClientSLA, "is_active").editable is True
    assert _3pl_field(ClientSLA, "status").editable is False


def test_3pl_sla_metric_choices_are_the_nine_derivable_promises():
    assert _3pl_values(SLA_METRIC_CHOICES) == [
        "on_time_shipment_pct", "otif_pct", "same_day_ship_pct", "order_accuracy_pct",
        "inventory_accuracy_pct", "dock_to_stock_hours", "order_cycle_time_hours",
        "damage_rate_pct", "shrinkage_pct"]


def test_3pl_sla_unit_direction_and_window_vocabularies():
    assert _3pl_values(SLA_UNIT_CHOICES) == ["pct", "hours", "days"]
    assert _3pl_values(SLA_DIRECTION_CHOICES) == ["higher_is_better", "lower_is_better"]
    assert _3pl_values(SLA_WINDOW_CHOICES) == ["monthly", "quarterly", "rolling_30", "rolling_90"]


def test_3pl_no_data_is_a_first_class_status():
    assert _3pl_values(SLA_STATUS_CHOICES) == ["meeting", "at_risk", "breached", "no_data"]
    assert set(SLA_STATUS_CSS) == set(_3pl_values(SLA_STATUS_CHOICES))
    assert set(SLA_STATUS_CSS.values()) <= _3pl_badge_classes
    assert SLA_STATUS_CSS["no_data"] == "badge-muted"
    assert SLA_STATUS_CSS["breached"] == "badge-red"


def test_3pl_the_metric_registry_is_closed_and_complete():
    assert set(SLA_METRIC_META) == set(_3pl_values(SLA_METRIC_CHOICES))
    for metric, meta in SLA_METRIC_META.items():
        assert set(meta) == {"label", "unit", "direction", "default_target", "source"}, metric
        assert meta["unit"] in _3pl_values(SLA_UNIT_CHOICES)
        assert meta["direction"] in _3pl_values(SLA_DIRECTION_CHOICES)
        assert isinstance(meta["default_target"], Decimal)
        assert meta["source"].strip()


def test_3pl_every_metric_has_a_resolver_that_exists():
    assert set(ClientSLA.RESOLVERS) == set(_3pl_values(SLA_METRIC_CHOICES))
    for metric, name in ClientSLA.RESOLVERS.items():
        assert callable(getattr(ClientSLA, name, None)), metric


def test_3pl_only_the_stock_metrics_can_be_narrowed_to_a_location():
    assert ClientSLA.LOCATION_SCOPABLE_METRICS == (
        "inventory_accuracy_pct", "dock_to_stock_hours", "damage_rate_pct", "shrinkage_pct")
    assert set(ClientSLA.LOCATION_SCOPABLE_METRICS) <= set(_3pl_values(SLA_METRIC_CHOICES))


def test_3pl_sla_ordering_reads_one_clients_promises_as_a_block():
    assert ClientSLA._meta.ordering == ["client__code", "metric", "id"]


def test_3pl_sla_metric_meta_is_empty_for_an_unknown_metric():
    assert ClientSLA(metric="not-a-metric").metric_meta == {}
    assert ClientSLA(metric="not-a-metric").status_css == "badge-muted"


# =================================================================================================
# 4.17 · ClientSLA — the derived reads
# =================================================================================================
def test_3pl_variance_is_none_until_something_is_measured(tpl_sla_a):
    assert tpl_sla_a.variance is None


def test_3pl_variance_is_signed_and_not_re_signed_for_a_lower_is_better_metric(tenant_a,
                                                                                tpl_client_a):
    higher = ClientSLA.objects.create(tenant=tenant_a, client=tpl_client_a, metric="otif_pct",
                                      target_value=Decimal("98.00"))
    ClientSLA.objects.filter(pk=higher.pk).update(last_measured_value=Decimal("96.0000"))
    higher.refresh_from_db()
    assert higher.variance == Decimal("-2.0000")

    lower = ClientSLA.objects.create(tenant=tenant_a, client=tpl_client_a,
                                     metric="damage_rate_pct", target_value=Decimal("0.50"),
                                     direction="lower_is_better")
    ClientSLA.objects.filter(pk=lower.pk).update(last_measured_value=Decimal("5.0000"))
    lower.refresh_from_db()
    assert lower.variance == Decimal("4.5000")


def test_3pl_is_breaching_reads_the_status(tpl_sla_a):
    assert tpl_sla_a.is_breaching is False
    ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(status="breached")
    tpl_sla_a.refresh_from_db()
    assert tpl_sla_a.is_breaching is True
    assert tpl_sla_a.status_css == "badge-red"


def test_3pl_a_monthly_window_is_the_last_full_calendar_month(tpl_sla_a, tpl_period):
    start, end = tpl_sla_a.resolve_window()[:2]
    assert (start, end) == tpl_period


def test_3pl_window_resolution_is_deterministic_for_an_injected_date(tpl_sla_a):
    as_of = datetime.date(2026, 5, 20)
    assert tpl_sla_a.resolve_window(as_of)[:2] == (datetime.date(2026, 4, 1),
                                                   datetime.date(2026, 4, 30))
    tpl_sla_a.measurement_window = "quarterly"
    assert tpl_sla_a.resolve_window(as_of)[:2] == (datetime.date(2026, 1, 1),
                                                   datetime.date(2026, 3, 31))
    tpl_sla_a.measurement_window = "rolling_30"
    assert tpl_sla_a.resolve_window(as_of)[:2] == (datetime.date(2026, 4, 20), as_of)
    tpl_sla_a.measurement_window = "rolling_90"
    assert tpl_sla_a.resolve_window(as_of)[:2] == (datetime.date(2026, 2, 19), as_of)


def test_3pl_window_label_flags_a_window_that_has_never_been_measured(tpl_sla_a):
    assert "not yet measured" in tpl_sla_a.window_label()


def test_3pl_window_label_reports_the_stored_window_once_there_is_one(tpl_sla_a, tpl_period):
    tpl_sla_a.recompute()
    tpl_sla_a.refresh_from_db()
    label = tpl_sla_a.window_label()
    assert "not yet measured" not in label
    assert f"{tpl_period[1]:%d %b %Y}" in label


def test_3pl_a_credit_is_suggested_only_for_a_breaching_promise(tpl_sla_a):
    assert tpl_sla_a.suggested_service_credit(Decimal("1000.00")) == Decimal("0")
    ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(status="breached")
    tpl_sla_a.refresh_from_db()
    assert tpl_sla_a.suggested_service_credit(Decimal("1000.00")) == Decimal("50.00")


def test_3pl_a_credit_cap_of_zero_means_no_cap(tpl_sla_a):
    """Reading a 0 cap literally would silently zero every credit in the application while every
    page went on displaying a credit percentage."""
    ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(status="breached",
                                                     service_credit_cap_pct=Decimal("0.00"))
    tpl_sla_a.refresh_from_db()
    assert tpl_sla_a.suggested_service_credit(Decimal("1000.00")) == Decimal("50.00")


def test_3pl_a_credit_cap_below_the_percentage_clamps_it(tpl_sla_a):
    ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(status="breached",
                                                     service_credit_cap_pct=Decimal("2.00"))
    tpl_sla_a.refresh_from_db()
    assert tpl_sla_a.suggested_service_credit(Decimal("1000.00")) == Decimal("20.00")


def test_3pl_no_fees_means_no_credit(tpl_sla_a):
    ClientSLA.objects.filter(pk=tpl_sla_a.pk).update(status="breached")
    tpl_sla_a.refresh_from_db()
    assert tpl_sla_a.suggested_service_credit(Decimal("0")) == Decimal("0")
    assert tpl_sla_a.suggested_service_credit(None) == Decimal("0")


@pytest.mark.parametrize("value, expected", [
    (Decimal("99"), "meeting"),
    (Decimal("98"), "meeting"),     # inclusive — 98.00 against a target of 98.00 is meeting it
    (Decimal("96"), "at_risk"),
    (Decimal("95"), "at_risk"),
    (Decimal("94"), "breached"),
])
def test_3pl_a_higher_is_better_metric_is_scored_inclusively(value, expected):
    sla = ClientSLA(metric="on_time_shipment_pct", target_value=Decimal("98.00"),
                    direction="higher_is_better", warning_threshold=Decimal("95.00"))
    assert sla._status_for(value) == expected


@pytest.mark.parametrize("value, expected", [
    (Decimal("20"), "meeting"),
    (Decimal("24"), "meeting"),
    (Decimal("30"), "at_risk"),
    (Decimal("31"), "breached"),
])
def test_3pl_a_lower_is_better_metric_is_scored_inclusively(value, expected):
    sla = ClientSLA(metric="dock_to_stock_hours", target_value=Decimal("24.00"),
                    direction="lower_is_better", warning_threshold=Decimal("30.00"))
    assert sla._status_for(value) == expected


def test_3pl_without_a_warning_band_there_is_no_at_risk_state():
    sla = ClientSLA(metric="on_time_shipment_pct", target_value=Decimal("98.00"),
                    direction="higher_is_better", warning_threshold=None)
    assert sla._status_for(Decimal("97")) == "breached"


# =================================================================================================
# 4.17 · ClientSLA.recompute() — evidence in, evidence out; never a confident zero
# =================================================================================================
def test_3pl_recompute_with_no_signal_answers_no_data_rather_than_zero(tpl_sla_a, tpl_period):
    result = tpl_sla_a.recompute()
    tpl_sla_a.refresh_from_db()
    assert result["status"] == "no_data"
    assert result["value"] is None
    assert tpl_sla_a.status == "no_data"
    assert tpl_sla_a.last_measured_value is None
    assert tpl_sla_a.last_measured_at is None
    assert tpl_sla_a.sample_size == 0
    assert tpl_sla_a.measurement_summary  # the REASON, not a blank
    assert (tpl_sla_a.measurement_window_start, tpl_sla_a.measurement_window_end) == tpl_period


def test_3pl_recompute_measures_a_loss_rate_from_the_stock_ledger(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_stock_move_a,
        tpl_period):
    start, _end = tpl_period
    _3pl_stock_move(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, "-5",
                    _3pl_moment(start + datetime.timedelta(days=8)), move_type="adjustment")
    sla = ClientSLA.objects.create(
        tenant=tenant_a, client=tpl_client_a, metric="damage_rate_pct",
        target_value=Decimal("0.50"), unit="pct", direction="lower_is_better",
        measurement_window="monthly")

    result = sla.recompute()
    sla.refresh_from_db()
    assert result["value"] == Decimal("5.0000")
    assert sla.last_measured_value == Decimal("5.0000")
    assert sla.last_measured_at is not None
    assert sla.status == "breached"
    assert sla.sample_size == 1
    assert sla.breach_count == 1
    assert (sla.measurement_window_start, sla.measurement_window_end) == tpl_period
    assert "received" in sla.measurement_summary


def test_3pl_recomputing_the_same_window_cannot_manufacture_a_second_breach(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_stock_move_a,
        tpl_period):
    start, _end = tpl_period
    _3pl_stock_move(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, "-5",
                    _3pl_moment(start + datetime.timedelta(days=8)), move_type="adjustment")
    sla = ClientSLA.objects.create(
        tenant=tenant_a, client=tpl_client_a, metric="shrinkage_pct",
        target_value=Decimal("0.65"), unit="pct", direction="lower_is_better")

    sla.recompute()
    sla.recompute()
    sla.recompute()
    sla.refresh_from_db()
    assert sla.status == "breached"
    assert sla.breach_count == 1


def test_3pl_a_later_no_data_window_never_clobbers_the_last_measurement(
        tenant_a, tpl_client_a, tpl_owned_item_a, tpl_dedicated_location_a, tpl_stock_move_a,
        tpl_period):
    start, _end = tpl_period
    _3pl_stock_move(tenant_a, tpl_owned_item_a, tpl_dedicated_location_a, "-5",
                    _3pl_moment(start + datetime.timedelta(days=8)), move_type="adjustment")
    sla = ClientSLA.objects.create(
        tenant=tenant_a, client=tpl_client_a, metric="damage_rate_pct",
        target_value=Decimal("0.50"), unit="pct", direction="lower_is_better")
    sla.recompute()
    sla.refresh_from_db()
    measured_at = sla.last_measured_at

    # A window with nothing in it: the month before the one the ledger row sits in.
    sla.recompute(as_of=start - datetime.timedelta(days=1))
    sla.refresh_from_db()
    assert sla.status == "no_data"
    assert sla.last_measured_value == Decimal("5.0000")
    assert sla.last_measured_at == measured_at
    assert sla.sample_size == 0
    assert sla.measurement_summary


def test_3pl_an_unhonoured_location_scope_is_said_rather_than_silently_ignored(
        tenant_a, tpl_client_a, tpl_dedicated_location_a):
    sla = ClientSLA.objects.create(
        tenant=tenant_a, client=tpl_client_a, metric="on_time_shipment_pct",
        target_value=Decimal("98.00"), scope_location=tpl_dedicated_location_a)
    sla.recompute()
    sla.refresh_from_db()
    assert "location scope does not apply to this metric" in sla.measurement_summary


@pytest.mark.parametrize("metric", [value for value, _label in SLA_METRIC_CHOICES])
def test_3pl_every_metric_answers_no_data_rather_than_zero_on_an_empty_workspace(
        tenant_a, tpl_client_a, metric):
    """Nine resolvers, one discipline: with nothing on file each of them returns ``no_data`` and a
    REASON. A confident 0 on a lower-is-better metric would additionally read as perfect."""
    meta = SLA_METRIC_META[metric]
    sla = ClientSLA.objects.create(
        tenant=tenant_a, client=tpl_client_a, metric=metric, unit=meta["unit"],
        direction=meta["direction"], target_value=meta["default_target"])

    result = sla.recompute()
    sla.refresh_from_db()
    assert result["status"] == "no_data"
    assert result["value"] is None
    assert sla.last_measured_value is None
    assert sla.sample_size == 0
    assert len(sla.measurement_summary) > 10


def test_3pl_order_accuracy_refuses_to_score_a_workspace_with_no_fault_vocabulary(tenant_a,
                                                                                   tpl_client_a):
    """With nothing on file that could ever mark a return as our mistake, an absence of such
    returns is an absence of evidence, not evidence of accuracy."""
    sla = ClientSLA.objects.create(tenant=tenant_a, client=tpl_client_a,
                                   metric="order_accuracy_pct", target_value=Decimal("99.50"))
    sla.recompute()
    sla.refresh_from_db()
    assert sla.status == "no_data"
    assert "merchant" in sla.measurement_summary


def test_3pl_recompute_can_answer_without_writing(tpl_sla_a):
    result = tpl_sla_a.recompute(save=False)
    tpl_sla_a.refresh_from_db()
    assert result["status"] == "no_data"
    assert tpl_sla_a.measurement_window_start is None


# =================================================================================================
# 4.17 · ClientSLA.clean() — seven guards
# =================================================================================================
def test_3pl_an_sla_for_another_workspaces_client_is_refused(tenant_a, tpl_client_b):
    sla = ClientSLA(tenant=tenant_a, client=tpl_client_b, metric="otif_pct",
                    target_value=Decimal("95.00"))
    with pytest.raises(ValidationError) as exc:
        sla.full_clean()
    assert "client" in exc.value.message_dict


def test_3pl_a_unit_the_registry_does_not_agree_with_is_refused(tenant_a, tpl_client_a):
    """A percentage metric saved with hours would compare 98 against 24 and breach forever."""
    sla = ClientSLA(tenant=tenant_a, client=tpl_client_a, metric="otif_pct",
                    target_value=Decimal("95.00"), unit="hours")
    with pytest.raises(ValidationError) as exc:
        sla.full_clean()
    assert "unit" in exc.value.message_dict


def test_3pl_a_direction_the_registry_does_not_agree_with_is_refused(tenant_a, tpl_client_a):
    sla = ClientSLA(tenant=tenant_a, client=tpl_client_a, metric="dock_to_stock_hours",
                    target_value=Decimal("24.00"), unit="hours", direction="higher_is_better")
    with pytest.raises(ValidationError) as exc:
        sla.full_clean()
    assert "direction" in exc.value.message_dict


def test_3pl_a_warning_band_on_the_meeting_side_is_refused(tpl_sla_a):
    tpl_sla_a.warning_threshold = Decimal("99.00")
    with pytest.raises(ValidationError) as exc:
        tpl_sla_a.full_clean()
    assert "warning_threshold" in exc.value.message_dict


def test_3pl_a_warning_band_below_a_lower_is_better_target_is_refused(tenant_a, tpl_client_a):
    sla = ClientSLA(tenant=tenant_a, client=tpl_client_a, metric="dock_to_stock_hours",
                    target_value=Decimal("24.00"), unit="hours", direction="lower_is_better",
                    warning_threshold=Decimal("12.00"))
    with pytest.raises(ValidationError) as exc:
        sla.full_clean()
    assert "warning_threshold" in exc.value.message_dict


def test_3pl_a_credit_cap_below_the_credit_percentage_is_refused(tpl_sla_a):
    tpl_sla_a.service_credit_cap_pct = Decimal("1.00")
    with pytest.raises(ValidationError) as exc:
        tpl_sla_a.full_clean()
    assert "service_credit_cap_pct" in exc.value.message_dict


def test_3pl_an_sla_scoped_to_another_clients_location_is_refused(tpl_sla_a,
                                                                   tpl_other_client_location_a):
    tpl_sla_a.scope_location = tpl_other_client_location_a
    with pytest.raises(ValidationError) as exc:
        tpl_sla_a.full_clean()
    assert "scope_location" in exc.value.message_dict


def test_3pl_an_sla_scoped_to_another_workspaces_location_is_refused(tpl_sla_a, location_b):
    tpl_sla_a.scope_location = location_b
    with pytest.raises(ValidationError) as exc:
        tpl_sla_a.full_clean()
    assert "scope_location" in exc.value.message_dict


def test_3pl_a_second_workspace_wide_promise_on_one_metric_is_refused(tenant_a, tpl_client_a,
                                                                       tpl_sla_a):
    """MySQL/MariaDB treat NULLs as DISTINCT in a unique index AND Django's validate_unique skips a
    tuple containing a NULL, so neither boundary catches this for free."""
    duplicate = ClientSLA(tenant=tenant_a, client=tpl_client_a, metric=tpl_sla_a.metric,
                          target_value=Decimal("97.00"))
    with pytest.raises(ValidationError) as exc:
        duplicate.full_clean()
    assert "metric" in exc.value.message_dict
    assert tpl_sla_a.number in exc.value.message_dict["metric"][0]


def test_3pl_the_same_metric_narrowed_to_a_location_is_allowed(tenant_a, tpl_client_a, tpl_sla_a,
                                                                tpl_dedicated_location_a):
    narrowed = ClientSLA(tenant=tenant_a, client=tpl_client_a, metric=tpl_sla_a.metric,
                         target_value=Decimal("97.00"), scope_location=tpl_dedicated_location_a)
    narrowed.full_clean()  # must not raise


def test_3pl_a_percentage_target_above_one_hundred_is_refused(tenant_a, tpl_client_a):
    sla = ClientSLA(tenant=tenant_a, client=tpl_client_a, metric="otif_pct",
                    target_value=Decimal("101.00"))
    with pytest.raises(ValidationError) as exc:
        sla.full_clean()
    assert "target_value" in exc.value.message_dict


def test_3pl_the_fixture_sla_validates_as_shipped(tpl_sla_a):
    tpl_sla_a.full_clean()  # must not raise
