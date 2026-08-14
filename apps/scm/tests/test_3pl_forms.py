"""SCM 4.17 Third-Party Logistics (3PL) Management — FORM tests.

This lane asserts three things and nothing else (the models, views and security lanes own the rest):

1. **What is on a form, and what must never be.** Every ``Meta.fields`` whitelist is pinned exactly,
   and the exclusions are asserted BY REASON — ``tenant`` (stamped by ``crud_create``), the auto
   number (``3PL-`` / ``TAR-`` / ``CBR-`` / ``SLA-``), the workflow ``status`` columns that belong to
   a verb ladder, every derived counter/amount, every ``editable=False`` evidence column and every
   system ``*_at`` timestamp (L20/L22). A secret in ``Meta.fields`` ships plaintext in the edit form,
   and a system timestamp on a ``DateInput`` is silently truncated to midnight.

   Two fields look like violations and are NOT: ``LogisticsClient.status`` and
   ``ClientRateCard.status`` are staff configuration and are on their forms deliberately, while
   ``ClientBillingRun.status`` and ``ClientSLA.status`` are ``editable=False`` ladder/measurement
   columns and are not. The tests below assert both directions so neither can be "fixed" into the
   other without a failure.

2. **The clean() rules**, at the boundary a user actually reaches: required fields, the period/basis
   agreement, the tier band, the date orderings, the metric registry, the overlap guard, the
   duplicate refusals that would otherwise be an uncaught ``IntegrityError`` (a 500) on an everyday
   mistake, and the negative / ``NaN`` / ``Infinity`` / over-``max_digits`` decimals that must come
   back as field errors rather than an exception.

3. **FK querysets are tenant-scoped** — a field offered to tenant A never contains tenant B's rows,
   a tenant-less caller is offered NOTHING, and a parent pk smuggled into a POST body is ignored in
   favour of the one the route resolved.

Naming: every test is ``test_3pl_*`` and every module-level helper/fixture ``_3pl_*`` (only the FIRST
character of an identifier may not be a digit). Fixtures from ``conftest.py`` carry the ``tpl_``
prefix because ``3pl_client_a`` is not a legal identifier. Dates derive from
``timezone.localdate()`` — never ``datetime.date.today()`` (L16).
"""
import datetime
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


# =================================================================================================
# Module-level helpers — every one prefixed `_3pl_` so a neighbouring sub-module's file cannot
# shadow it (test_suite_hygiene.py enforces uniqueness within a file; the prefix protects across).
# =================================================================================================

#: Substrings that must never appear in ANY 4.17 form field name (L20). A credential rendered into
#: an edit form ships as plaintext in the HTML, and a hash rendered into one is overwritten by
#: whatever the user posts back.
_3pl_SECRET_TOKENS = (
    "password", "passwd", "secret", "token", "api_key", "apikey", "credential",
    "hash", "salt", "signature", "private_key", "access_key", "endpoint", "webhook",
)

#: The exact ``Meta.fields`` whitelists, in declaration order. Pinned here rather than read off the
#: form so a field added to a form is a FAILURE rather than a silently accepted change.
_3pl_EXPECTED_FIELDS = {
    "LogisticsClientForm": [
        "party", "code", "parent_client", "status",
        "billing_cycle", "billing_day", "next_billing_date", "storage_billing_method",
        "minimum_monthly_charge", "default_tax_rate_pct",
        "currency", "payment_terms", "default_revenue_account",
        "space_model", "committed_sqft", "committed_pallet_positions",
        "contract_start", "contract_end", "notice_days", "contract_document",
        "integration_mode", "client_system", "edi_partner_id", "edi_qualifier",
        "account_manager", "notes",
    ],
    "ClientRateCardForm": [
        "client", "name", "version", "status", "effective_from", "effective_to", "currency",
        "notes",
    ],
    "ClientRateCardLineForm": [
        "charge_category", "charge_basis", "description", "rate", "period", "included_quantity",
        "minimum_charge", "tier_from", "tier_to", "applies_to_location",
        "applies_to_item_category", "gl_account", "is_active",
    ],
    "ClientBillingRunForm": ["client", "rate_card", "period_start", "period_end", "notes"],
    "ClientBillingRunLineForm": [
        "charge_category", "charge_basis", "description", "quantity", "rate", "source_reference",
    ],
    "ClientSLAForm": [
        "client", "metric", "name", "target_value", "unit", "direction", "warning_threshold",
        "measurement_window", "scope_location", "service_credit_pct", "service_credit_cap_pct",
        "is_active", "notes",
    ],
}


def _3pl_unbound_forms(tenant=None):
    """One UNBOUND instance of each 4.17 form, keyed by class name.

    The two child forms take their parent from the route, so they are constructed unparented here —
    which is itself the documented posture: an unparented line form refuses every FK it is offered.
    """
    from apps.scm.forms import (
        ClientBillingRunForm,
        ClientBillingRunLineForm,
        ClientRateCardForm,
        ClientRateCardLineForm,
        ClientSLAForm,
        LogisticsClientForm,
    )
    return {
        "LogisticsClientForm": LogisticsClientForm(tenant=tenant),
        "ClientRateCardForm": ClientRateCardForm(tenant=tenant),
        "ClientRateCardLineForm": ClientRateCardLineForm(tenant=tenant, rate_card=None),
        "ClientBillingRunForm": ClientBillingRunForm(tenant=tenant),
        "ClientBillingRunLineForm": ClientBillingRunLineForm(tenant=tenant, run=None),
        "ClientSLAForm": ClientSLAForm(tenant=tenant),
    }


def _3pl_errors_text(form):
    """Every error message on ``form`` as one lowercase string — for asserting the REASON, not just
    the field. A refusal that comes back with the wrong explanation is a bug the user pays for."""
    return " ".join(
        message for messages in form.errors.values() for message in messages).lower()


def _3pl_client_post(party_pk, **overrides):
    """A minimal VALID ``LogisticsClientForm`` POST: every required key, nothing optional.

    Every value is a STRING, because that is what a ``QueryDict`` hands a form — a test that posts
    integers is testing a request shape that cannot occur, and it hides code that reads ``self.data``
    as text before ``cleaned_data`` exists.
    """
    data = {
        "party": str(party_pk),
        "code": "NEW1",
        "status": "prospect",
        "billing_cycle": "monthly",
        "billing_day": "1",
        "storage_billing_method": "calendar_month",
        "minimum_monthly_charge": "0.00",
        "default_tax_rate_pct": "0.00",
        "space_model": "shared",
        "committed_sqft": "0.00",
        "committed_pallet_positions": "0",
        "notice_days": "0",
        "integration_mode": "none",
    }
    data.update(overrides)
    # A QueryDict only ever holds strings, so an int pk passed as an override is coerced
    # here rather than at every call site.
    return {key: str(value) for key, value in data.items()}


def _3pl_client_edit_post(client, **overrides):
    """A POST that re-states an EXISTING client's own values — the edit-page round trip.

    Built off the instance rather than hard-coded so a test can change exactly one key and know the
    rest is a row the model already accepted.
    """
    return _3pl_client_post(
        client.party_id,
        code=client.code,
        status=client.status,
        billing_cycle=client.billing_cycle,
        billing_day=str(client.billing_day),
        storage_billing_method=client.storage_billing_method,
        minimum_monthly_charge=str(client.minimum_monthly_charge),
        default_tax_rate_pct=str(client.default_tax_rate_pct),
        space_model=client.space_model,
        committed_sqft=str(client.committed_sqft),
        committed_pallet_positions=str(client.committed_pallet_positions),
        notice_days=str(client.notice_days),
        integration_mode=client.integration_mode,
        **overrides,
    )


def _3pl_card_post(client_pk, effective_from, **overrides):
    """A minimal VALID ``ClientRateCardForm`` POST (string values — see :func:`_3pl_client_post`)."""
    data = {
        "client": str(client_pk),
        "name": "Second tariff",
        "version": "2",
        "status": "draft",
        "effective_from": effective_from.isoformat(),
    }
    data.update(overrides)
    # A QueryDict only ever holds strings, so an int pk passed as an override is coerced
    # here rather than at every call site.
    return {key: str(value) for key, value in data.items()}


def _3pl_card_line_post(**overrides):
    """A minimal VALID ``ClientRateCardLineForm`` POST — an EVENT basis, so ``period`` stays blank."""
    data = {
        "charge_category": "receiving",
        "charge_basis": "per_receipt",
        "description": "Inbound receipt handling",
        "rate": "12.0000",
        "period": "",
        "included_quantity": "0",
        "minimum_charge": "0",
        "tier_from": "0",
        # A checkbox that is not in the body reads as UNCHECKED, never as the model default: the
        # form renders `is_active` checked (initial=True), so a normal create posts it.
        "is_active": "on",
    }
    data.update(overrides)
    # A QueryDict only ever holds strings, so an int pk passed as an override is coerced
    # here rather than at every call site.
    return {key: str(value) for key, value in data.items()}


def _3pl_run_post(client_pk, rate_card_pk, period_start, period_end, **overrides):
    """A minimal VALID ``ClientBillingRunForm`` POST (string values — a ``QueryDict`` has no ints)."""
    data = {
        "client": str(client_pk),
        "rate_card": str(rate_card_pk),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }
    data.update(overrides)
    # A QueryDict only ever holds strings, so an int pk passed as an override is coerced
    # here rather than at every call site.
    return {key: str(value) for key, value in data.items()}


def _3pl_run_line_post(**overrides):
    """A minimal VALID ``ClientBillingRunLineForm`` POST — a manual charge, 2 x 25.00."""
    data = {
        "charge_category": "value_added",
        "charge_basis": "per_hour",
        "description": "Kitting and rework labour",
        "quantity": "2.0000",
        "rate": "25.0000",
        "source_reference": "photo log",
    }
    data.update(overrides)
    # A QueryDict only ever holds strings, so an int pk passed as an override is coerced
    # here rather than at every call site.
    return {key: str(value) for key, value in data.items()}


def _3pl_sla_post(client_pk, **overrides):
    """A minimal VALID ``ClientSLAForm`` POST.

    ``damage_rate_pct`` on purpose: ``tpl_sla_a`` already occupies ``on_time_shipment_pct`` with a
    NULL scope for the same client, and that pairing is refused by ``ClientSLA.clean()``.
    """
    data = {
        "client": str(client_pk),
        "metric": "damage_rate_pct",
        "name": "Damage rate",
        "target_value": "0.50",
        "unit": "pct",
        "direction": "lower_is_better",
        "measurement_window": "monthly",
        "service_credit_pct": "0.00",
        "service_credit_cap_pct": "0.00",
        "is_active": "on",
    }
    data.update(overrides)
    # A QueryDict only ever holds strings, so an int pk passed as an override is coerced
    # here rather than at every call site.
    return {key: str(value) for key, value in data.items()}


# =================================================================================================
# Local fixtures — only what conftest.py does not already provide (it is final and off-limits).
# =================================================================================================
@pytest.fixture
def _3pl_shared_card_a(db, tenant_a, tpl_client_shared_a):
    """A DRAFT tariff belonging to tenant_a's OTHER client.

    Same workspace, different client — the counterparty for "a tariff of another client" on a
    billing run, and for the dedicated-space refusal (``tpl_client_shared_a.space_model`` is
    ``shared``).
    """
    from django.utils import timezone
    from apps.scm.models import ClientRateCard
    today = timezone.localdate()
    return ClientRateCard.objects.create(
        tenant=tenant_a, client=tpl_client_shared_a, name="Shared tariff", version=1,
        status="draft", effective_from=today - datetime.timedelta(days=30), effective_to=None)


@pytest.fixture
def _3pl_payment_term_b(db, tenant_b):
    """tenant_b's payment term — must never appear in a tenant_a dropdown."""
    from apps.accounting.models import PaymentTerm
    return PaymentTerm.objects.create(tenant=tenant_b, name="Net 60", days_due=60)


@pytest.fixture
def _3pl_revenue_account_b(db, tenant_b):
    """tenant_b's income account — the cross-tenant target for every GL dropdown here."""
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(tenant=tenant_b, code="4100", name="Globex Revenue",
                                    account_type="income")


@pytest.fixture
def _3pl_inactive_currency(db):
    """A retired GLOBAL currency. ``accounting.Currency`` has no tenant column, so the only
    narrowing a 3PL form can apply to it is ``is_active`` — assert that it does."""
    from apps.accounting.models import Currency
    obj, _ = Currency.objects.get_or_create(
        code="ZWD", defaults={"name": "Zimbabwe Dollar", "symbol": "Z$", "is_active": False})
    return obj


# =================================================================================================
# Cross-form shape guards — L20 / L22, asserted over ALL SIX forms at once
# =================================================================================================
class Test3plFormShapeAcrossTheSubModule:
    def test_3pl_every_form_matches_its_pinned_field_whitelist(self):
        """A field added to (or dropped from) any 4.17 form is a FAILURE, not a silent change.

        The whitelists are ``Meta.fields`` lists rather than ``Meta.exclude``: a whitelist fails
        CLOSED when a column is added to the model later, which is the whole reason a system field
        cannot become user-editable by accident.
        """
        for name, form in _3pl_unbound_forms().items():
            assert list(form.fields) == _3pl_EXPECTED_FIELDS[name], name

    def test_3pl_no_form_exposes_tenant_or_the_auto_number(self):
        """``tenant`` is stamped by ``crud_create`` / ``TenantUniqueMixin``; the number is minted in
        ``TenantNumbered.save()``. Either on a form is a mass-assignment hole."""
        for name, form in _3pl_unbound_forms().items():
            assert "tenant" not in form.fields, name
            assert "number" not in form.fields, name

    def test_3pl_no_form_exposes_a_secret_or_credential_field(self):
        """L20. 4.17 stores NO API key, endpoint, EDI password or token — only non-secret partner
        identifiers — and no form may ever render one."""
        for name, form in _3pl_unbound_forms().items():
            for field_name in form.fields:
                lowered = field_name.lower()
                for token in _3pl_SECRET_TOKENS:
                    assert token not in lowered, f"{name}.{field_name} looks like a secret"

    def test_3pl_no_form_exposes_a_system_timestamp(self):
        """L22. A ``DateTimeField`` put on a form's ``DateInput`` is silently truncated to midnight,
        so every system ``*_at`` column stays ``editable=False`` and off every form."""
        for name, form in _3pl_unbound_forms().items():
            for field_name in form.fields:
                assert not field_name.endswith("_at"), f"{name}.{field_name}"
            for field_name in ("created_at", "updated_at", "last_synced_at", "calculated_at",
                               "approved_at", "last_measured_at", "onboarded_on"):
                assert field_name not in form.fields, f"{name}.{field_name}"

    def test_3pl_a_tenantless_caller_is_offered_nothing(self):
        """The superuser has ``tenant=None`` by design. Every tenant-scoped dropdown must fall to
        EMPTY rather than to the unscoped default manager, which would pool every workspace's rows
        into one select."""
        from django import forms as django_forms
        for name, form in _3pl_unbound_forms(tenant=None).items():
            for field_name, field in form.fields.items():
                if not isinstance(field, django_forms.ModelChoiceField):
                    continue
                if field.queryset.model.__name__ == "Currency":
                    continue  # GLOBAL master — no tenant column to scope by
                assert not field.queryset.exists(), f"{name}.{field_name} leaked rows"


# =================================================================================================
# LogisticsClientForm
# =================================================================================================
class Test3plLogisticsClientFormShape:
    def test_3pl_logisticsclient_form_excludes_the_four_system_columns(self):
        """``onboarded_on`` is EVIDENCE of go-live (stamped once in ``save()``), ``last_synced_at``
        is 4.19's transport timestamp, and neither ``tenant`` nor ``number`` is ever typed."""
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(tenant=None)
        for field_name in ("tenant", "number", "onboarded_on", "last_synced_at"):
            assert field_name not in form.fields

    def test_3pl_logisticsclient_form_keeps_status_on_the_form_deliberately(self):
        """The OPPOSITE of ``ClientBillingRun.status``: a 3PL client's lifecycle is staff
        configuration with no approval to route through. Asserted so it cannot be "tidied away" to
        match a sibling model whose status is a verb ladder."""
        from apps.scm.forms import LogisticsClientForm
        assert "status" in LogisticsClientForm(tenant=None).fields

    def test_3pl_logisticsclient_form_carries_only_non_secret_integration_identifiers(self):
        from apps.scm.forms import LogisticsClientForm
        fields = LogisticsClientForm(tenant=None).fields
        for field_name in ("integration_mode", "client_system", "edi_partner_id", "edi_qualifier"):
            assert field_name in fields


class Test3plLogisticsClientFormValidation:
    def test_3pl_logisticsclient_form_reports_every_required_field(self, tenant_a):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(data={}, tenant=tenant_a)
        assert not form.is_valid()
        required = {"party", "code", "status", "billing_cycle", "billing_day",
                    "storage_billing_method", "minimum_monthly_charge", "default_tax_rate_pct",
                    "space_model", "committed_sqft", "committed_pallet_positions", "notice_days",
                    "integration_mode"}
        assert required <= set(form.errors)
        for optional in ("parent_client", "next_billing_date", "currency", "payment_terms",
                         "contract_start", "contract_end", "notes"):
            assert optional not in form.errors

    def test_3pl_logisticsclient_form_saves_with_the_request_tenant_and_an_auto_number(
            self, tenant_a, tpl_customer_a2):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(data=_3pl_client_post(tpl_customer_a2.pk), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("3PL-")
        assert obj.onboarded_on is None  # prospect — nothing has gone live yet

    def test_3pl_logisticsclient_form_refuses_a_duplicate_code_instead_of_500ing(
            self, tenant_a, tpl_client_a, tpl_customer_a2):
        """``unique_together ("tenant", "code")``. Without ``TenantUniqueMixin`` this passes
        ``is_valid()`` and raises an uncaught ``IntegrityError`` on ``save()``."""
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, code=tpl_client_a.code), tenant=tenant_a)
        assert not form.is_valid()
        assert "code" in _3pl_errors_text(form)

    def test_3pl_logisticsclient_form_refuses_a_second_agreement_for_one_party(
            self, tenant_a, tpl_client_a, customer_a):
        """``unique_together ("tenant", "party")`` — ONE 3PL agreement per company."""
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(data=_3pl_client_post(customer_a.pk, code="DUP1"),
                                   tenant=tenant_a)
        assert not form.is_valid()

    def test_3pl_logisticsclient_form_refuses_dedicated_space_with_no_commitment(
            self, tenant_a, tpl_customer_a2):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, space_model="dedicated"), tenant=tenant_a)
        assert not form.is_valid()
        assert "space_model" in form.errors
        assert "commitment" in _3pl_errors_text(form)

    def test_3pl_logisticsclient_form_refuses_a_commitment_on_a_shared_space_model(
            self, tenant_a, tpl_customer_a2):
        """The mirror rule: a figure the user typed and the system silently dropped is worse than an
        error, because they leave believing it applied."""
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, space_model="shared",
                                  committed_sqft="1000.00"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "space_model" in form.errors

    def test_3pl_logisticsclient_form_refuses_an_over_range_committed_area(
            self, tenant_a, tpl_customer_a2):
        """Above ``MAX_COMMITTED_SQFT`` but still inside the column, so this is ``clean()``'s
        refusal rather than a ``DataError`` raised by the driver on save."""
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, space_model="dedicated",
                                  committed_sqft="99999999.99"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "committed_sqft" in form.errors

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "abc", "1e400"])
    def test_3pl_logisticsclient_form_refuses_junk_decimals_without_raising(
            self, tenant_a, tpl_customer_a2, value):
        """Never a 500: every one of these comes back as a field error on the re-rendered form."""
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, minimum_monthly_charge=value),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "minimum_monthly_charge" in form.errors

    def test_3pl_logisticsclient_form_refuses_a_negative_minimum_charge(
            self, tenant_a, tpl_customer_a2):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, minimum_monthly_charge="-1.00"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "minimum_monthly_charge" in form.errors

    def test_3pl_logisticsclient_form_refuses_a_billing_day_past_28(
            self, tenant_a, tpl_customer_a2):
        """Capped at 28 so every month has one — a client billed on the 30th has no billing day in
        February."""
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, billing_day="30"), tenant=tenant_a)
        assert not form.is_valid()
        assert "billing_day" in form.errors

    def test_3pl_logisticsclient_form_refuses_a_status_outside_the_vocabulary(
            self, tenant_a, tpl_customer_a2):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, status="zzz"), tenant=tenant_a)
        assert not form.is_valid()
        assert "status" in form.errors

    def test_3pl_logisticsclient_form_refuses_a_contract_ending_before_it_starts(
            self, tenant_a, tpl_customer_a2):
        from django.utils import timezone
        from apps.scm.forms import LogisticsClientForm
        today = timezone.localdate()
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk,
                                  contract_start=today.isoformat(),
                                  contract_end=(today - datetime.timedelta(days=1)).isoformat()),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "contract_end" in form.errors

    def test_3pl_logisticsclient_form_refuses_a_client_as_its_own_parent(
            self, tenant_a, tpl_client_a):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_edit_post(tpl_client_a, parent_client=tpl_client_a.pk),
            instance=tpl_client_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "parent_client" in form.errors

    def test_3pl_logisticsclient_form_refuses_a_loop_in_the_client_hierarchy(
            self, tenant_a, tpl_client_a, tpl_client_shared_a):
        """A -> B -> A. The walk is bounded by ``MAX_CLIENT_DEPTH``; an unbounded one would be an
        infinite loop INSIDE form validation, i.e. a hung request from an ordinary edit."""
        from apps.scm.forms import LogisticsClientForm
        tpl_client_shared_a.parent_client = tpl_client_a
        tpl_client_shared_a.save(update_fields=["parent_client"])
        form = LogisticsClientForm(
            data=_3pl_client_edit_post(tpl_client_a, parent_client=tpl_client_shared_a.pk),
            instance=tpl_client_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "parent_client" in form.errors
        assert "loop" in _3pl_errors_text(form)

    def test_3pl_logisticsclient_form_stamps_onboarded_on_the_first_time_it_saves_active(
            self, tenant_a, tpl_customer_a2):
        """The date is EVIDENCE, not an input: it is off the form and written once in ``save()``."""
        from django.utils import timezone
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, status="active"), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.onboarded_on == timezone.localdate()


class Test3plLogisticsClientFormScoping:
    def test_3pl_logisticsclient_form_party_choices_are_customers_of_this_workspace_only(
            self, tenant_a, customer_a, tpl_customer_a2, supplier_a, customer_b):
        """Narrowed by ROLE on top of the tenant scoping — without it the dropdown offers the whole
        party book, suppliers and carriers included."""
        from apps.scm.forms import LogisticsClientForm
        parties = list(LogisticsClientForm(tenant=tenant_a).fields["party"].queryset)
        assert customer_a in parties
        assert tpl_customer_a2 in parties
        assert supplier_a not in parties
        assert customer_b not in parties

    def test_3pl_logisticsclient_form_parent_choices_exclude_self_and_other_workspaces(
            self, tenant_a, tpl_client_a, tpl_client_shared_a, tpl_client_b):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(instance=tpl_client_a, tenant=tenant_a)
        parents = list(form.fields["parent_client"].queryset)
        assert tpl_client_shared_a in parents
        assert tpl_client_a not in parents
        assert tpl_client_b not in parents

    def test_3pl_logisticsclient_form_money_dropdowns_are_tenant_scoped(
            self, tenant_a, payment_terms_a, tpl_revenue_account_a, _3pl_payment_term_b,
            _3pl_revenue_account_b):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(tenant=tenant_a)
        terms = list(form.fields["payment_terms"].queryset)
        accounts = list(form.fields["default_revenue_account"].queryset)
        assert payment_terms_a in terms and _3pl_payment_term_b not in terms
        assert tpl_revenue_account_a in accounts and _3pl_revenue_account_b not in accounts

    def test_3pl_logisticsclient_form_account_manager_choices_are_this_workspaces_users(
            self, tenant_a, admin_user, member_user, admin_b):
        from apps.scm.forms import LogisticsClientForm
        managers = list(LogisticsClientForm(tenant=tenant_a).fields["account_manager"].queryset)
        assert admin_user in managers
        assert member_user in managers
        assert admin_b not in managers

    def test_3pl_logisticsclient_form_currency_choices_are_active_only(
            self, tenant_a, usd, _3pl_inactive_currency):
        """``accounting.Currency`` is GLOBAL — no tenant column — so ``is_active`` is the only
        narrowing available, and it has to be applied by hand."""
        from apps.scm.forms import LogisticsClientForm
        currencies = list(LogisticsClientForm(tenant=tenant_a).fields["currency"].queryset)
        assert usd in currencies
        assert _3pl_inactive_currency not in currencies

    def test_3pl_logisticsclient_form_rejects_a_crafted_cross_tenant_party(
            self, tenant_a, customer_b):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(data=_3pl_client_post(customer_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert "party" in form.errors

    def test_3pl_logisticsclient_form_rejects_a_crafted_cross_tenant_account_manager(
            self, tenant_a, tpl_customer_a2, admin_b):
        from apps.scm.forms import LogisticsClientForm
        form = LogisticsClientForm(
            data=_3pl_client_post(tpl_customer_a2.pk, account_manager=admin_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert "account_manager" in form.errors

    def test_3pl_logisticsclient_form_keeps_an_already_stored_choice_on_edit(
            self, tenant_a, tpl_client_a, customer_a):
        """A narrowing that dropped the stored value would silently NULL it for somebody who only
        came to fix a typo — a field nobody touched, changed by loading a page."""
        from apps.core.models import PartyRole
        from apps.scm.forms import LogisticsClientForm
        PartyRole.objects.filter(party=customer_a, role="customer").delete()
        form = LogisticsClientForm(instance=tpl_client_a, tenant=tenant_a)
        assert customer_a in list(form.fields["party"].queryset)


# =================================================================================================
# ClientRateCardForm
# =================================================================================================
class Test3plClientRateCardFormShape:
    def test_3pl_clientratecard_form_excludes_tenant_number_and_timestamps(self):
        from apps.scm.forms import ClientRateCardForm
        form = ClientRateCardForm(tenant=None)
        for field_name in ("tenant", "number", "created_at", "updated_at"):
            assert field_name not in form.fields

    def test_3pl_clientratecard_form_keeps_status_on_the_form_deliberately(self):
        """The activate/supersede verbs are the PREFERRED path, not the only one — and the overlap
        guard lives in ``clean()``, so promoting a card through the form is still safe. The exact
        opposite of ``ClientBillingRunForm``; neither may be "fixed" to match the other."""
        from apps.scm.forms import ClientRateCardForm
        assert "status" in ClientRateCardForm(tenant=None).fields


class Test3plClientRateCardFormValidation:
    def test_3pl_clientratecard_form_reports_every_required_field(self, tenant_a):
        from apps.scm.forms import ClientRateCardForm
        form = ClientRateCardForm(data={}, tenant=tenant_a)
        assert not form.is_valid()
        assert {"client", "name", "version", "status", "effective_from"} <= set(form.errors)
        for optional in ("effective_to", "currency", "notes"):
            assert optional not in form.errors

    def test_3pl_clientratecard_form_saves_with_the_request_tenant_and_a_tar_number(
            self, tenant_a, tpl_client_a):
        from django.utils import timezone
        from apps.scm.forms import ClientRateCardForm
        today = timezone.localdate()
        form = ClientRateCardForm(data=_3pl_card_post(tpl_client_a.pk, today), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("TAR-")
        assert obj.status == "draft"

    def test_3pl_clientratecard_form_refuses_an_end_before_its_start(self, tenant_a, tpl_client_a):
        from django.utils import timezone
        from apps.scm.forms import ClientRateCardForm
        today = timezone.localdate()
        form = ClientRateCardForm(
            data=_3pl_card_post(tpl_client_a.pk, today,
                                effective_to=(today - datetime.timedelta(days=1)).isoformat()),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "effective_to" in form.errors

    def test_3pl_clientratecard_form_refuses_a_second_active_card_over_the_same_days(
            self, tenant_a, tpl_client_a, tpl_active_card_a):
        """Two active cards over one day means the billing run has two prices for it and picks one
        by accident — the single mistake this status ladder exists to prevent."""
        from django.utils import timezone
        from apps.scm.forms import ClientRateCardForm
        today = timezone.localdate()
        form = ClientRateCardForm(
            data=_3pl_card_post(tpl_client_a.pk, today - datetime.timedelta(days=10),
                                status="active"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "effective_from" in form.errors
        assert tpl_active_card_a.number.lower() in _3pl_errors_text(form)

    def test_3pl_clientratecard_form_allows_a_draft_beside_a_live_card(
            self, tenant_a, tpl_client_a, tpl_active_card_a):
        """A draft is a PROPOSAL — several may sit side by side while prices are negotiated, so the
        overlap guard is keyed on ``status == "active"`` and nothing else."""
        from django.utils import timezone
        from apps.scm.forms import ClientRateCardForm
        today = timezone.localdate()
        form = ClientRateCardForm(
            data=_3pl_card_post(tpl_client_a.pk, today - datetime.timedelta(days=10)),
            tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_3pl_clientratecard_form_refuses_a_duplicate_name_and_version(
            self, tenant_a, tpl_active_card_a):
        """``unique_together ("tenant", "client", "name", "version")`` — without the mixin this is
        an uncaught ``IntegrityError`` on an everyday re-save."""
        from apps.scm.forms import ClientRateCardForm
        form = ClientRateCardForm(
            data=_3pl_card_post(tpl_active_card_a.client_id, tpl_active_card_a.effective_from,
                                name=tpl_active_card_a.name,
                                version=str(tpl_active_card_a.version)),
            tenant=tenant_a)
        assert not form.is_valid()

    def test_3pl_clientratecard_form_rejects_a_crafted_cross_tenant_client(
            self, tenant_a, tpl_client_b):
        from django.utils import timezone
        from apps.scm.forms import ClientRateCardForm
        form = ClientRateCardForm(
            data=_3pl_card_post(tpl_client_b.pk, timezone.localdate()), tenant=tenant_a)
        assert not form.is_valid()
        assert "client" in form.errors

    def test_3pl_clientratecard_form_refuses_a_junk_effective_date(self, tenant_a, tpl_client_a):
        from apps.scm.forms import ClientRateCardForm
        form = ClientRateCardForm(
            data={"client": tpl_client_a.pk, "name": "Junk", "version": "1", "status": "draft",
                  "effective_from": "lastweek"},
            tenant=tenant_a)
        assert not form.is_valid()
        assert "effective_from" in form.errors

    def test_3pl_clientratecard_form_client_choices_are_tenant_scoped(
            self, tenant_a, tpl_client_a, tpl_client_shared_a, tpl_client_b):
        from apps.scm.forms import ClientRateCardForm
        clients = list(ClientRateCardForm(tenant=tenant_a).fields["client"].queryset)
        assert tpl_client_a in clients and tpl_client_shared_a in clients
        assert tpl_client_b not in clients

    def test_3pl_clientratecard_form_currency_choices_are_active_only(
            self, tenant_a, usd, _3pl_inactive_currency):
        from apps.scm.forms import ClientRateCardForm
        currencies = list(ClientRateCardForm(tenant=tenant_a).fields["currency"].queryset)
        assert usd in currencies
        assert _3pl_inactive_currency not in currencies


# =================================================================================================
# ClientRateCardLineForm — the parent comes from the ROUTE, never from the POST body
# =================================================================================================
class Test3plClientRateCardLineFormShape:
    def test_3pl_clientratecardline_form_has_no_rate_card_field(self):
        """A SECURITY boundary, not a tidy-up: a parent pk in a POST body is how a caller grafts a
        priced line onto somebody else's tariff."""
        from apps.scm.forms import ClientRateCardLineForm
        assert "rate_card" not in ClientRateCardLineForm(tenant=None, rate_card=None).fields

    def test_3pl_clientratecardline_form_ignores_a_rate_card_smuggled_into_the_body(
            self, tenant_a, tpl_rate_card_a, tpl_rate_card_b):
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(rate_card=tpl_rate_card_b.pk),
            rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        line = form.save()
        assert line.rate_card_id == tpl_rate_card_a.pk


class Test3plClientRateCardLineFormValidation:
    def test_3pl_clientratecardline_form_reports_every_required_field(
            self, tenant_a, tpl_rate_card_a):
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(data={}, rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert {"charge_category", "charge_basis", "description"} <= set(form.errors)

    def test_3pl_clientratecardline_form_saves_an_event_basis_with_a_blank_period(
            self, tenant_a, tpl_rate_card_a):
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(data=_3pl_card_line_post(), rate_card=tpl_rate_card_a,
                                      tenant=tenant_a)
        assert form.is_valid(), form.errors
        line = form.save()
        assert line.rate_card_id == tpl_rate_card_a.pk
        assert line.period == ""
        assert line.is_active is True

    def test_3pl_clientratecardline_form_refuses_a_period_on_a_per_event_basis(
            self, tenant_a, tpl_rate_card_a):
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(period="month"), rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "period" in form.errors
        assert "per event" in _3pl_errors_text(form)

    def test_3pl_clientratecardline_form_refuses_a_periodic_basis_with_no_period(
            self, tenant_a, tpl_rate_card_a):
        """A "3.50 per pallet position" with no period is not a price — per day and per month differ
        by a factor of thirty."""
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(charge_category="storage",
                                     charge_basis="per_pallet_position", period=""),
            rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "period" in form.errors

    def test_3pl_clientratecardline_form_refuses_an_empty_tier_band(
            self, tenant_a, tpl_rate_card_a):
        """Half-open ``[tier_from, tier_to)``, so an upper bound at or below the lower one covers no
        quantity at all and could never match."""
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(tier_from="100", tier_to="100"),
            rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "tier_to" in form.errors

    def test_3pl_clientratecardline_form_refuses_dedicated_space_for_a_shared_client(
            self, tenant_a, _3pl_shared_card_a):
        """The line somebody copies from another client's card — a charge with no basis in this
        client's contract."""
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(charge_category="storage", charge_basis="dedicated_space",
                                     period="month"),
            rate_card=_3pl_shared_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "charge_basis" in form.errors

    def test_3pl_clientratecardline_form_refuses_another_clients_dedicated_bin(
            self, tenant_a, tpl_rate_card_a, tpl_other_client_location_a):
        """Same workspace, different owner: pricing this client's storage against somebody else's
        aisle would bill them for space that is not theirs."""
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(applies_to_location=tpl_other_client_location_a.pk),
            rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "applies_to_location" in form.errors

    def test_3pl_clientratecardline_form_refuses_a_cross_tenant_location(
            self, tenant_a, tpl_rate_card_a, location_b):
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(applies_to_location=location_b.pk),
            rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "applies_to_location" in form.errors

    def test_3pl_clientratecardline_form_refuses_a_cross_tenant_item_category(
            self, tenant_a, tpl_rate_card_a, category_b):
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(applies_to_item_category=category_b.pk),
            rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "applies_to_item_category" in form.errors

    def test_3pl_clientratecardline_form_refuses_a_cross_tenant_gl_account(
            self, tenant_a, tpl_rate_card_a, _3pl_revenue_account_b):
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(gl_account=_3pl_revenue_account_b.pk),
            rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "gl_account" in form.errors

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "abc", "12345678901.0000"])
    def test_3pl_clientratecardline_form_refuses_junk_rates_without_raising(
            self, tenant_a, tpl_rate_card_a, value):
        """``rate`` is ``max_digits=14, decimal_places=4`` — ten integer digits. Over-range, junk,
        negative and the two non-finite spellings must all be FIELD errors, never a 500."""
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(
            data=_3pl_card_line_post(rate=value), rate_card=tpl_rate_card_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "rate" in form.errors

    def test_3pl_clientratecardline_form_refuses_a_line_past_the_tariff_cap(
            self, tenant_a, tpl_rate_card_a):
        """``MAX_RATE_CARD_LINES``. Keyed on ``__all__`` because it is about the PARENT, and
        ``rate_card`` is not a form field — any other key raises ``ValueError`` out of
        ``add_error``."""
        from django.core.exceptions import NON_FIELD_ERRORS
        from apps.scm.forms import ClientRateCardLineForm
        from apps.scm.models import ClientRateCardLine
        from apps.scm.models.ThirdPartyLogistics._choices import MAX_RATE_CARD_LINES
        ClientRateCardLine.objects.bulk_create([
            ClientRateCardLine(rate_card=tpl_rate_card_a, charge_category="accessorial",
                               charge_basis="per_order", description=f"Filler {index}",
                               rate=Decimal("1.0000"))
            for index in range(MAX_RATE_CARD_LINES)
        ])
        form = ClientRateCardLineForm(data=_3pl_card_line_post(), rate_card=tpl_rate_card_a,
                                      tenant=tenant_a)
        assert not form.is_valid()
        assert NON_FIELD_ERRORS in form.errors
        assert str(MAX_RATE_CARD_LINES) in _3pl_errors_text(form)


class Test3plClientRateCardLineFormScoping:
    def test_3pl_clientratecardline_form_location_choices_exclude_other_clients_bins(
            self, tenant_a, tpl_rate_card_a, location_a, tpl_dedicated_location_a,
            tpl_other_client_location_a, location_b):
        """Shared bins and this client's OWN dedicated bins stay; another client's do not — and
        neither does another workspace's."""
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(rate_card=tpl_rate_card_a, tenant=tenant_a)
        locations = list(form.fields["applies_to_location"].queryset)
        assert location_a in locations
        assert tpl_dedicated_location_a in locations
        assert tpl_other_client_location_a not in locations
        assert location_b not in locations

    def test_3pl_clientratecardline_form_scopes_by_the_parents_workspace_not_the_kwarg(
            self, tenant_b, tpl_rate_card_a, category_a, category_b):
        """The route already resolved the card with ``tenant=request.tenant``, so the PARENT's
        workspace is the authority — a mismatched ``tenant=`` kwarg must not widen anything."""
        from apps.scm.forms import ClientRateCardLineForm
        form = ClientRateCardLineForm(rate_card=tpl_rate_card_a, tenant=tenant_b)
        categories = list(form.fields["applies_to_item_category"].queryset)
        assert category_a in categories
        assert category_b not in categories

    def test_3pl_clientratecardline_form_without_a_parent_accepts_no_fk_at_all(
            self, tenant_a, location_a):
        """An unparented line form is itself a refusal, not a pass: with no parent there is no
        workspace to check a chosen row against, so ``clean()`` refuses every FK it is offered.

        Only the BOUNDARY is asserted here, deliberately. The dropdown-emptiness half of the same
        rule is not: ``_scope_to_tenant`` falls back to ``form.tenant`` when the parent's tenant is
        ``None`` (``forms/ThirdPartyLogistics/ClientRateCards.py:78-80``), which contradicts the
        constructor's own comment that it "falls to ``.none()`` when there is no parent". That is
        reported rather than pinned in either direction — the route always supplies a parent, so it
        is presentation-only defence in depth, and this test must pass whichever way it is resolved.
        """
        from apps.scm.forms import ClientRateCardLineForm
        bound = ClientRateCardLineForm(
            data=_3pl_card_line_post(applies_to_location=location_a.pk),
            rate_card=None, tenant=tenant_a)
        assert not bound.is_valid()
        assert "applies_to_location" in bound.errors


# =================================================================================================
# ClientBillingRunForm — five fields and NO money
# =================================================================================================
class Test3plClientBillingRunFormShape:
    def test_3pl_clientbillingrun_form_excludes_every_derived_and_workflow_column(self):
        """Nine workflow columns plus the three amounts. A typed subtotal would be a second,
        un-auditable answer to what the client owes."""
        from apps.scm.forms import ClientBillingRunForm
        form = ClientBillingRunForm(tenant=None)
        for field_name in ("status", "subtotal", "minimum_adjustment", "total", "calculated_at",
                           "approved_at", "approved_by", "invoice", "number", "tenant",
                           "created_at", "updated_at"):
            assert field_name not in form.fields

    def test_3pl_clientbillingrun_form_carries_no_money_field_at_all(self):
        from apps.scm.forms import ClientBillingRunForm
        form = ClientBillingRunForm(tenant=None)
        assert list(form.fields) == ["client", "rate_card", "period_start", "period_end", "notes"]


class Test3plClientBillingRunFormValidation:
    def test_3pl_clientbillingrun_form_reports_every_required_field(self, tenant_a):
        from apps.scm.forms import ClientBillingRunForm
        form = ClientBillingRunForm(data={}, tenant=tenant_a)
        assert not form.is_valid()
        assert {"client", "rate_card", "period_start", "period_end"} <= set(form.errors)
        assert "notes" not in form.errors

    def test_3pl_clientbillingrun_form_saves_a_draft_with_a_cbr_number_and_zero_money(
            self, tenant_a, tpl_client_a, tpl_active_card_a):
        from django.utils import timezone
        from apps.scm.forms import ClientBillingRunForm
        today = timezone.localdate()
        form = ClientBillingRunForm(
            data=_3pl_run_post(tpl_client_a.pk, tpl_active_card_a.pk,
                               today - datetime.timedelta(days=10), today),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        run = form.save()
        assert run.tenant_id == tenant_a.pk
        assert run.number.startswith("CBR-")
        assert run.status == "draft"
        assert (run.subtotal, run.minimum_adjustment, run.total) == (
            Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))

    def test_3pl_clientbillingrun_form_refuses_a_period_that_ends_before_it_starts(
            self, tenant_a, tpl_client_a, tpl_active_card_a):
        from django.utils import timezone
        from apps.scm.forms import ClientBillingRunForm
        today = timezone.localdate()
        form = ClientBillingRunForm(
            data=_3pl_run_post(tpl_client_a.pk, tpl_active_card_a.pk, today,
                               today - datetime.timedelta(days=5)),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "period_end" in form.errors

    def test_3pl_clientbillingrun_form_refuses_a_period_longer_than_the_cap(
            self, tenant_a, tpl_client_a, tpl_active_card_a):
        """``MAX_RUN_PERIOD_DAYS`` is 366 — a full leap year is legal, a mistyped 2062 is not. The
        period feeds day-by-day walks, so an unbounded one is a loop somebody starts from a form."""
        from django.utils import timezone
        from apps.scm.forms import ClientBillingRunForm
        today = timezone.localdate()
        form = ClientBillingRunForm(
            data=_3pl_run_post(tpl_client_a.pk, tpl_active_card_a.pk,
                               today - datetime.timedelta(days=400), today),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "period_end" in form.errors
        assert "366" in _3pl_errors_text(form)

    def test_3pl_clientbillingrun_form_refuses_a_tariff_that_does_not_cover_the_period(
            self, tenant_a, tpl_client_a, tpl_rate_card_a):
        """``tpl_rate_card_a`` starts TOMORROW, so it prices nothing in a period ending today."""
        from django.utils import timezone
        from apps.scm.forms import ClientBillingRunForm
        today = timezone.localdate()
        form = ClientBillingRunForm(
            data=_3pl_run_post(tpl_client_a.pk, tpl_rate_card_a.pk,
                               today - datetime.timedelta(days=10), today),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "rate_card" in form.errors
        assert "does not overlap" in _3pl_errors_text(form)

    def test_3pl_clientbillingrun_form_refuses_another_clients_tariff(
            self, tenant_a, tpl_client_a, _3pl_shared_card_a):
        """THE one that matters: billing Acme at Contoso's rates produces figures that look
        entirely plausible."""
        from django.utils import timezone
        from apps.scm.forms import ClientBillingRunForm
        today = timezone.localdate()
        form = ClientBillingRunForm(
            data=_3pl_run_post(tpl_client_a.pk, _3pl_shared_card_a.pk,
                               today - datetime.timedelta(days=10), today),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "rate_card" in form.errors

    def test_3pl_clientbillingrun_form_refuses_re_running_a_period_already_billed(
            self, tenant_a, tpl_billing_run_a, tpl_period):
        """``unique_together ("tenant", "client", "period_start", "period_end")`` — the single most
        ordinary mistake on this page, and an uncaught ``IntegrityError`` without the mixin."""
        from apps.scm.forms import ClientBillingRunForm
        start, end = tpl_period
        form = ClientBillingRunForm(
            data=_3pl_run_post(tpl_billing_run_a.client_id, tpl_billing_run_a.rate_card_id,
                               start, end),
            tenant=tenant_a)
        assert not form.is_valid()

    def test_3pl_clientbillingrun_form_rejects_a_crafted_cross_tenant_client_and_tariff(
            self, tenant_a, tpl_client_b, tpl_rate_card_b, tpl_period):
        from apps.scm.forms import ClientBillingRunForm
        start, end = tpl_period
        form = ClientBillingRunForm(
            data=_3pl_run_post(tpl_client_b.pk, tpl_rate_card_b.pk, start, end), tenant=tenant_a)
        assert not form.is_valid()
        assert "client" in form.errors
        assert "rate_card" in form.errors

    def test_3pl_clientbillingrun_form_refuses_a_junk_period_date(
            self, tenant_a, tpl_client_a, tpl_active_card_a):
        from apps.scm.forms import ClientBillingRunForm
        form = ClientBillingRunForm(
            data={"client": tpl_client_a.pk, "rate_card": tpl_active_card_a.pk,
                  "period_start": "lastweek", "period_end": "2026-13-45"},
            tenant=tenant_a)
        assert not form.is_valid()
        assert "period_start" in form.errors
        assert "period_end" in form.errors

    def test_3pl_clientbillingrun_form_narrows_the_tariff_list_to_the_chosen_client(
            self, tenant_a, tpl_client_a, tpl_active_card_a, tpl_rate_card_a, _3pl_shared_card_a,
            tpl_rate_card_b):
        from apps.scm.forms import ClientBillingRunForm
        form = ClientBillingRunForm(data={"client": str(tpl_client_a.pk)}, tenant=tenant_a)
        cards = list(form.fields["rate_card"].queryset)
        assert tpl_active_card_a in cards and tpl_rate_card_a in cards
        assert _3pl_shared_card_a not in cards
        assert tpl_rate_card_b not in cards

    def test_3pl_clientbillingrun_form_client_and_tariff_choices_are_tenant_scoped(
            self, tenant_a, tpl_client_a, tpl_client_b, tpl_active_card_a, tpl_rate_card_b):
        from apps.scm.forms import ClientBillingRunForm
        form = ClientBillingRunForm(tenant=tenant_a)
        assert tpl_client_a in list(form.fields["client"].queryset)
        assert tpl_client_b not in list(form.fields["client"].queryset)
        assert tpl_active_card_a in list(form.fields["rate_card"].queryset)
        assert tpl_rate_card_b not in list(form.fields["rate_card"].queryset)


# =================================================================================================
# ClientBillingRunLineForm — ONE manual charge; the derived lines are calculate()'s
# =================================================================================================
class Test3plClientBillingRunLineFormShape:
    def test_3pl_clientbillingrunline_form_excludes_the_parent_and_every_engine_column(self):
        """``run`` is an IDOR if it is in the body; ``rate_card_line`` NULL is what MAKES a line
        manual; ``amount`` is computed in ``save()``; ``is_manual`` is forced by the view; and
        ``needs_manual_quantity`` is the engine's."""
        from apps.scm.forms import ClientBillingRunLineForm
        form = ClientBillingRunLineForm(tenant=None, run=None)
        for field_name in ("run", "rate_card_line", "amount", "is_manual",
                           "needs_manual_quantity"):
            assert field_name not in form.fields

    def test_3pl_clientbillingrunline_form_ignores_a_run_smuggled_into_the_body(
            self, tenant_a, tpl_billing_run_a, tpl_billing_run_b):
        from apps.scm.forms import ClientBillingRunLineForm
        form = ClientBillingRunLineForm(
            data=_3pl_run_line_post(run=tpl_billing_run_b.pk), run=tpl_billing_run_a,
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        line = form.save()
        assert line.run_id == tpl_billing_run_a.pk


class Test3plClientBillingRunLineFormValidation:
    def test_3pl_clientbillingrunline_form_reports_every_required_field(
            self, tenant_a, tpl_billing_run_a):
        from apps.scm.forms import ClientBillingRunLineForm
        form = ClientBillingRunLineForm(data={}, run=tpl_billing_run_a, tenant=tenant_a)
        assert not form.is_valid()
        assert {"charge_category", "charge_basis", "description"} <= set(form.errors)
        assert "source_reference" not in form.errors

    def test_3pl_clientbillingrunline_form_saves_with_the_amount_derived_in_save(
            self, tenant_a, tpl_billing_run_a):
        """``amount`` has exactly one writer — ``ClientBillingRunLine.save()`` — and it is not a
        form field, so the figure cannot be typed."""
        from apps.scm.forms import ClientBillingRunLineForm
        form = ClientBillingRunLineForm(data=_3pl_run_line_post(), run=tpl_billing_run_a,
                                        tenant=tenant_a)
        assert form.is_valid(), form.errors
        line = form.save()
        assert line.amount == Decimal("50.00")
        assert line.rate_card_line_id is None

    def test_3pl_clientbillingrunline_form_ignores_an_amount_posted_in_the_body(
            self, tenant_a, tpl_billing_run_a):
        from apps.scm.forms import ClientBillingRunLineForm
        form = ClientBillingRunLineForm(
            data=_3pl_run_line_post(amount="99999.00", is_manual="on"), run=tpl_billing_run_a,
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        line = form.save()
        assert line.amount == Decimal("50.00")
        assert line.is_manual is False  # the VIEW forces this, never the body

    def test_3pl_clientbillingrunline_form_refuses_a_negative_quantity_and_says_why(
            self, tenant_a, tpl_billing_run_a):
        """A negative would floor to 0.00 in ``save()`` — silently. A credit to a 3PL client is a
        credit note in Accounting."""
        from apps.scm.forms import ClientBillingRunLineForm
        form = ClientBillingRunLineForm(
            data=_3pl_run_line_post(quantity="-2.0000"), run=tpl_billing_run_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "quantity" in form.errors
        assert "credit note" in _3pl_errors_text(form)

    def test_3pl_clientbillingrunline_form_refuses_a_negative_rate_and_says_why(
            self, tenant_a, tpl_billing_run_a):
        from apps.scm.forms import ClientBillingRunLineForm
        form = ClientBillingRunLineForm(
            data=_3pl_run_line_post(rate="-25.0000"), run=tpl_billing_run_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "rate" in form.errors
        assert "credit note" in _3pl_errors_text(form)

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "abc", "12345678901234.0000"])
    def test_3pl_clientbillingrunline_form_refuses_junk_quantities_without_raising(
            self, tenant_a, tpl_billing_run_a, value):
        """``quantity`` is ``max_digits=16, decimal_places=4`` — twelve integer digits."""
        from apps.scm.forms import ClientBillingRunLineForm
        form = ClientBillingRunLineForm(
            data=_3pl_run_line_post(quantity=value), run=tpl_billing_run_a, tenant=tenant_a)
        assert not form.is_valid()
        assert "quantity" in form.errors

    def test_3pl_clientbillingrunline_form_refuses_a_charge_basis_outside_the_registry(
            self, tenant_a, tpl_billing_run_a):
        """The rating model is a CLOSED registry — each basis is a resolver somebody wrote."""
        from apps.scm.forms import ClientBillingRunLineForm
        form = ClientBillingRunLineForm(
            data=_3pl_run_line_post(charge_basis="per_fortnight"), run=tpl_billing_run_a,
            tenant=tenant_a)
        assert not form.is_valid()
        assert "charge_basis" in form.errors


# =================================================================================================
# ClientSLAForm — the promise is typed, the evidence never is
# =================================================================================================
class Test3plClientSLAFormShape:
    def test_3pl_clientsla_form_excludes_all_eight_evidence_columns(self):
        """Every one is ``editable=False`` and written only by ``recompute()``. A measured figure a
        user can retype is not a measurement."""
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(tenant=None)
        for field_name in ("last_measured_value", "last_measured_at", "measurement_window_start",
                           "measurement_window_end", "measurement_summary", "sample_size",
                           "breach_count", "status"):
            assert field_name not in form.fields

    def test_3pl_clientsla_form_keeps_is_active_but_not_status(self):
        """The two look alike and are opposites: ``is_active`` is the human's switch, ``status`` is
        a measurement."""
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(tenant=None)
        assert "is_active" in form.fields
        assert "status" not in form.fields

    def test_3pl_clientsla_form_prints_the_metric_registry_under_unit_and_direction(self):
        """The rule ``clean()`` ENFORCES is the rule the form ADVERTISES — one string built from
        ``SLA_METRIC_META`` rather than a copy in a template that can drift."""
        from apps.scm.forms import ClientSLAForm
        from apps.scm.forms.ThirdPartyLogistics.ClientSlas import METRIC_REGISTRY_HELP
        form = ClientSLAForm(tenant=None)
        assert form.fields["unit"].help_text == METRIC_REGISTRY_HELP
        assert form.fields["direction"].help_text == METRIC_REGISTRY_HELP
        assert "On-Time Shipment %" in METRIC_REGISTRY_HELP


class Test3plClientSLAFormValidation:
    def test_3pl_clientsla_form_reports_every_required_field(self, tenant_a):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(data={}, tenant=tenant_a)
        assert not form.is_valid()
        assert {"client", "metric", "target_value", "unit", "direction", "measurement_window",
                "service_credit_pct", "service_credit_cap_pct"} <= set(form.errors)
        for optional in ("name", "warning_threshold", "scope_location", "is_active", "notes"):
            assert optional not in form.errors

    def test_3pl_clientsla_form_saves_with_the_request_tenant_and_an_sla_number(
            self, tenant_a, tpl_client_a):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(data=_3pl_sla_post(tpl_client_a.pk), tenant=tenant_a)
        assert form.is_valid(), form.errors
        sla = form.save()
        assert sla.tenant_id == tenant_a.pk
        assert sla.number.startswith("SLA-")
        assert sla.status == "no_data"
        assert sla.last_measured_value is None
        assert sla.breach_count == 0

    def test_3pl_clientsla_form_refuses_a_unit_the_registry_does_not_agree_with(
            self, tenant_a, tpl_client_a):
        """A percentage metric saved in hours would compare 98 against 24 and breach forever."""
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(
            data=_3pl_sla_post(tpl_client_a.pk, unit="hours"), tenant=tenant_a)
        assert not form.is_valid()
        assert "unit" in form.errors

    def test_3pl_clientsla_form_refuses_a_direction_the_registry_does_not_agree_with(
            self, tenant_a, tpl_client_a):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(
            data=_3pl_sla_post(tpl_client_a.pk, direction="higher_is_better"), tenant=tenant_a)
        assert not form.is_valid()
        assert "direction" in form.errors

    def test_3pl_clientsla_form_refuses_a_warning_band_that_could_never_fire(
            self, tenant_a, tpl_client_a):
        """Lower is better here, so the at-risk band has to sit ABOVE the target — a threshold on
        the passing side implies an early warning that does not exist."""
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(
            data=_3pl_sla_post(tpl_client_a.pk, warning_threshold="0.10"), tenant=tenant_a)
        assert not form.is_valid()
        assert "warning_threshold" in form.errors

    def test_3pl_clientsla_form_refuses_a_credit_cap_below_the_credit_percentage(
            self, tenant_a, tpl_client_a):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(
            data=_3pl_sla_post(tpl_client_a.pk, service_credit_pct="10.00",
                               service_credit_cap_pct="5.00"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "service_credit_cap_pct" in form.errors

    def test_3pl_clientsla_form_accepts_a_zero_cap_as_no_ceiling(self, tenant_a, tpl_client_a):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(
            data=_3pl_sla_post(tpl_client_a.pk, service_credit_pct="10.00",
                               service_credit_cap_pct="0.00"),
            tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_3pl_clientsla_form_refuses_a_percentage_target_above_100(
            self, tenant_a, tpl_client_a):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(
            data=_3pl_sla_post(tpl_client_a.pk, target_value="120.00"), tenant=tenant_a)
        assert not form.is_valid()
        assert "target_value" in form.errors

    def test_3pl_clientsla_form_refuses_a_second_workspace_wide_promise_on_one_metric(
            self, tenant_a, tpl_client_a, tpl_sla_a):
        """MySQL treats NULLs as distinct in a unique index AND Django skips a ``unique_together``
        containing a NULL, so neither boundary catches this for free — ``clean()`` does."""
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(
            data=_3pl_sla_post(tpl_client_a.pk, metric="on_time_shipment_pct", unit="pct",
                               direction="higher_is_better", target_value="98.00"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "metric" in form.errors
        assert tpl_sla_a.number.lower() in _3pl_errors_text(form)

    def test_3pl_clientsla_form_refuses_a_metric_outside_the_closed_registry(
            self, tenant_a, tpl_client_a):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(data=_3pl_sla_post(tpl_client_a.pk, metric="uptime_pct"),
                             tenant=tenant_a)
        assert not form.is_valid()
        assert "metric" in form.errors

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "abc", "-1.00"])
    def test_3pl_clientsla_form_refuses_junk_targets_without_raising(
            self, tenant_a, tpl_client_a, value):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(data=_3pl_sla_post(tpl_client_a.pk, target_value=value),
                             tenant=tenant_a)
        assert not form.is_valid()
        assert "target_value" in form.errors

    def test_3pl_clientsla_form_rejects_a_crafted_cross_tenant_client(self, tenant_a, tpl_client_b):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(data=_3pl_sla_post(tpl_client_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert "client" in form.errors

    def test_3pl_clientsla_form_refuses_another_clients_dedicated_bin_as_a_scope(
            self, tenant_a, tpl_client_a, tpl_other_client_location_a):
        """Measuring this client's promise against somebody else's aisle would score them on stock
        that is not theirs."""
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(
            data=_3pl_sla_post(tpl_client_a.pk, metric="inventory_accuracy_pct", unit="pct",
                               direction="higher_is_better", target_value="99.00",
                               scope_location=tpl_other_client_location_a.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "scope_location" in form.errors

    def test_3pl_clientsla_form_refuses_a_cross_tenant_scope_location(
            self, tenant_a, tpl_client_a, location_b):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(
            data=_3pl_sla_post(tpl_client_a.pk, scope_location=location_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert "scope_location" in form.errors


class Test3plClientSLAFormScoping:
    def test_3pl_clientsla_form_client_choices_are_tenant_scoped(
            self, tenant_a, tpl_client_a, tpl_client_shared_a, tpl_client_b):
        from apps.scm.forms import ClientSLAForm
        clients = list(ClientSLAForm(tenant=tenant_a).fields["client"].queryset)
        assert tpl_client_a in clients and tpl_client_shared_a in clients
        assert tpl_client_b not in clients

    def test_3pl_clientsla_form_scope_choices_drop_other_clients_bins_once_a_client_is_named(
            self, tenant_a, tpl_client_a, location_a, tpl_dedicated_location_a,
            tpl_other_client_location_a, location_b):
        from apps.scm.forms import ClientSLAForm
        form = ClientSLAForm(data={"client": str(tpl_client_a.pk)}, tenant=tenant_a)
        locations = list(form.fields["scope_location"].queryset)
        assert location_a in locations
        assert tpl_dedicated_location_a in locations
        assert tpl_other_client_location_a not in locations
        assert location_b not in locations

    def test_3pl_clientsla_form_blank_create_page_still_scopes_to_the_workspace(
            self, tenant_a, location_a, tpl_other_client_location_a, location_b):
        """With no client chosen there is no such thing as "another client's bin" yet, so the owner
        narrowing is DELIBERATELY skipped — but the tenant scoping never is. ``clean()`` is the real
        boundary and refuses a foreign bin by name."""
        from apps.scm.forms import ClientSLAForm
        locations = list(ClientSLAForm(tenant=tenant_a).fields["scope_location"].queryset)
        assert location_a in locations
        assert tpl_other_client_location_a in locations
        assert location_b not in locations

    def test_3pl_clientsla_form_keeps_a_stored_scope_on_edit(
            self, tenant_a, tpl_client_a, tpl_dedicated_location_a, tpl_sla_a):
        """A narrowed queryset that no longer contains the stored value would silently re-point a
        location-scoped promise at the whole workspace, restating every figure derived from it."""
        from apps.scm.forms import ClientSLAForm
        tpl_sla_a.scope_location = tpl_dedicated_location_a
        tpl_sla_a.save(update_fields=["scope_location"])
        form = ClientSLAForm(instance=tpl_sla_a, tenant=tenant_a)
        assert tpl_dedicated_location_a in list(form.fields["scope_location"].queryset)
