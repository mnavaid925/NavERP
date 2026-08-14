"""SCM 4.18 Finance & Accounting Integration — FORM tests.

This lane owns the form boundary and nothing else (the models, views and security lanes own the
rest). Three questions, asked of all THREE 4.18 forms — ``DutyTariffForm``,
``LandedCostVoucherForm`` and ``LandedCostChargeForm``:

1. **What is on a form, and what must never be.** Every ``Meta.fields`` whitelist is pinned exactly
   and every exclusion is asserted BY REASON: ``tenant`` (stamped by ``crud_create`` and, on the
   tariff, by ``TenantUniqueMixin.__init__`` before validation), the auto numbers (``DTY-#####`` /
   ``LC-#####``, minted in ``TenantNumbered.save()``), the workflow ``status`` that belongs to the
   verb ladder, the ``bill`` hand-off, all five ``recalc_totals()``-derived money columns, and the
   system ``accrued_at`` timestamp (L20/L22 — a secret in ``Meta.fields`` ships plaintext in the edit
   form, and a system ``*_at`` on a ``DateInput`` is silently truncated to midnight on the next save).

   ``LandedCostChargeForm``'s ONE exclusion is a security decision rather than a tidiness one:
   ``voucher`` comes from the ROUTE, because a parent pk in a POST body is how a caller grafts a
   charge onto another workspace's voucher. That is asserted in both directions — the field is
   absent, AND a ``voucher`` key smuggled into the body is ignored in favour of the route's parent.

2. **The clean() rules at the boundary a user actually reaches** — required fields, the inverted
   effective window, the HS-code normalisation that makes the ``unique_together`` bite, the duplicate
   refusal that would otherwise be an uncaught ``IntegrityError`` (a 500) on an everyday mistake, the
   duty rate that only belongs on a Customs Duty charge, the blank duty rate coerced to the model's
   NOT NULL default, the ``DutyTariff.rate_for()`` defaulting, and the negative / ``NaN`` /
   ``Infinity`` / over-``max_digits`` decimals that must come back as FIELD ERRORS rather than an
   exception.

3. **FK ModelChoiceField querysets are tenant-scoped** — a field offered to tenant A never contains
   a tenant B row, a tenant-less caller (the superuser has ``tenant=None`` BY DESIGN) is offered
   NOTHING, the narrowings hold (received receipts only, carrier-roled parties only, active GL
   accounts and tax codes only), ``_keep_current`` re-admits an already-stored row that stopped
   qualifying, and ``_reject_foreign`` still refuses a foreign pk when the narrowed ``<select>`` is
   widened out from under it — a narrowed dropdown is UX, never an authorization boundary.

Naming: every test is ``test_finance_*`` and every module-level helper / constant / fixture
``_finance_*`` (``test_suite_hygiene.py`` fails on any module-level name defined twice, and the prefix
protects the sub-module that appends next). Dates derive from ``timezone.localdate()`` — the SAME
basis ``DutyTariff.is_current`` / ``rate_for()`` read — never ``datetime.date.today()`` (L16).
"""
import datetime
from decimal import Decimal

import pytest
from django import forms as django_forms
from django.utils import timezone

pytestmark = pytest.mark.django_db


# =================================================================================================
# Module-level helpers and constants — every one prefixed `_finance_`
# =================================================================================================

#: Substrings that must never appear in ANY 4.18 form field name (L20). A credential rendered into an
#: edit form ships as plaintext in the HTML; a hash rendered into one is overwritten by whatever the
#: user posts back. 4.18 stores none of these — the assertion exists so a later field cannot.
_finance_SECRET_TOKENS = (
    "password", "passwd", "secret", "token", "api_key", "apikey", "credential",
    "hash", "salt", "signature", "private_key", "access_key", "endpoint", "webhook",
)

#: The exact ``Meta.fields`` whitelists, in declaration order. Pinned HERE rather than read off the
#: form so that a field added to (or dropped from) a form is a FAILURE, not a silent change.
_finance_EXPECTED_FIELDS = {
    "DutyTariffForm": [
        "hs_code", "country_of_origin", "description", "duty_rate_pct",
        "effective_from", "effective_to", "tax_code", "is_active",
    ],
    "LandedCostVoucherForm": [
        "goods_receipt", "party", "shipment", "trade_document", "currency", "cost_date",
        "allocation_basis", "notes",
    ],
    "LandedCostChargeForm": [
        "charge_type", "description", "party", "freight_invoice", "estimated_amount",
        "actual_amount", "allocation_basis", "gl_account", "tax_code", "is_recoverable",
        "capitalise_to_inventory", "hs_code", "country_of_origin", "duty_rate_pct",
    ],
}

#: Columns that exist on the 4.18 models and must NEVER reach a form. Asserted by name so a later
#: hand dropping ``editable=False`` for an admin convenience cannot silently open them.
_finance_FORBIDDEN_FIELDS = (
    "tenant", "number", "status", "bill", "voucher",
    "estimated_total", "actual_total", "variance_amount", "variance_pct", "allocated_total",
    "accrued_at", "created_at", "updated_at",
)


def _finance_unbound_forms(tenant=None, voucher=None):
    """One UNBOUND instance of each 4.18 form, keyed by class name.

    The charge form takes its parent from the route, so it is constructed unparented by default —
    which is itself the documented posture, not a shortcut.
    """
    from apps.scm.forms import DutyTariffForm, LandedCostChargeForm, LandedCostVoucherForm
    return {
        "DutyTariffForm": DutyTariffForm(tenant=tenant),
        "LandedCostVoucherForm": LandedCostVoucherForm(tenant=tenant),
        "LandedCostChargeForm": LandedCostChargeForm(tenant=tenant, voucher=voucher),
    }


def _finance_errors_text(form):
    """Every error message on ``form`` as ONE lowercase string.

    For asserting the REASON, not just the field — a refusal that comes back with the wrong
    explanation is a bug the user pays for.
    """
    return " ".join(
        message for messages in form.errors.values() for message in messages).lower()


def _finance_tariff_post(effective_from, **overrides):
    """A minimal VALID ``DutyTariffForm`` POST.

    Every value is a STRING because that is what a ``QueryDict`` hands a form — a test that posts
    ``Decimal``/``int`` objects is testing a request shape that cannot occur.
    """
    data = {
        "hs_code": "8528.72",
        "country_of_origin": "France",
        "description": "Reception apparatus for television",
        "duty_rate_pct": "3.750",
        "effective_from": effective_from.isoformat(),
        "effective_to": "",
        "tax_code": "",
        # A checkbox absent from the body reads as UNCHECKED, never as the model default — the form
        # renders `is_active` checked (initial=True), so a normal create posts it.
        "is_active": "on",
    }
    data.update(overrides)
    return {key: str(value) for key, value in data.items()}


def _finance_voucher_post(goods_receipt_pk, party_pk, cost_date, **overrides):
    """A minimal VALID ``LandedCostVoucherForm`` POST — the envelope only, no money anywhere."""
    data = {
        "goods_receipt": str(goods_receipt_pk),
        "party": str(party_pk),
        "shipment": "",
        "trade_document": "",
        "currency": "",
        "cost_date": cost_date.isoformat(),
        "allocation_basis": "value",
        "notes": "Ocean freight and customs on the January container.",
    }
    data.update(overrides)
    return {key: str(value) for key, value in data.items()}


def _finance_charge_post(**overrides):
    """A minimal VALID ``LandedCostChargeForm`` POST — a capitalising freight estimate of 100.00.

    ``is_recoverable`` is deliberately ABSENT: an unchecked checkbox is simply not in the body, and
    a test that posts ``"is_recoverable": "off"`` would be posting a shape a browser never sends.
    """
    data = {
        "charge_type": "freight",
        "description": "Ocean freight",
        "party": "",
        "freight_invoice": "",
        "estimated_amount": "100.00",
        "actual_amount": "0.00",
        "allocation_basis": "",
        "gl_account": "",
        "tax_code": "",
        "hs_code": "",
        "country_of_origin": "",
        # Blank on purpose — `clean_duty_rate_pct` coerces it to the model's NOT NULL default.
        "duty_rate_pct": "",
        "capitalise_to_inventory": "on",
    }
    data.update(overrides)
    return {key: str(value) for key, value in data.items()}


def _finance_choice_values(form, name):
    """The choice VALUES of a plain ChoiceField, in order (the blank option included if present)."""
    return [value for value, _label in form.fields[name].choices]


# =================================================================================================
# Local fixtures — only what conftest.py does not already provide (it is final and off-limits)
# =================================================================================================
@pytest.fixture
def _finance_inactive_currency(db):
    """A retired GLOBAL currency. ``accounting.Currency`` has no tenant column, so the ONLY narrowing
    a 4.18 form can apply to it is ``is_active`` — assert that it does."""
    from apps.accounting.models import Currency
    obj, _ = Currency.objects.get_or_create(
        code="ZWD", defaults={"name": "Zimbabwe Dollar", "symbol": "Z$", "is_active": False})
    return obj


@pytest.fixture
def _finance_tariff_with_tax_code_a(db, tenant_a, finance_tax_code_a):
    """A tenant_a tariff POINTING AT a tax code — the edit-path subject for ``_keep_current``.

    ``finance_duty_tariff_a`` deliberately carries no ``tax_code``, and a re-admission test needs a
    row that already holds the value the narrowing later excludes.
    """
    from apps.scm.models import DutyTariff
    return DutyTariff.objects.create(
        tenant=tenant_a, hs_code="9403.20", country_of_origin="Italy",
        description="Metal furniture", duty_rate_pct=Decimal("4.000"),
        effective_from=timezone.localdate() - datetime.timedelta(days=5),
        tax_code=finance_tax_code_a, is_active=True)


@pytest.fixture
def _finance_charge_with_accounts_a(db, finance_voucher_a, supplier_a, gl_expense,
                                    finance_tax_code_a, freight_invoice_a):
    """A tenant_a charge holding EVERY optional FK the charge form narrows.

    ``party`` is narrowed by ROLE and ``gl_account`` / ``tax_code`` by ``is_active``; all three are
    ``null=True``. Once a stored row stops qualifying its ``<option>`` disappears, the browser posts
    an empty value, and saving an unrelated edit NULLs the FK with no error to warn anybody — which
    is the whole reason ``_keep_current`` exists and the reason this fixture holds all four.
    """
    from apps.scm.models import LandedCostCharge
    charge = LandedCostCharge.objects.create(
        voucher=finance_voucher_a, charge_type="brokerage", description="Customs brokerage",
        party=supplier_a, freight_invoice=freight_invoice_a, gl_account=gl_expense,
        tax_code=finance_tax_code_a, estimated_amount=Decimal("75.00"))
    finance_voucher_a.recalc_totals()
    return charge


# =================================================================================================
# Cross-form shape guards — L20 / L22, asserted over ALL THREE forms at once
# =================================================================================================
class TestFinanceFormShapeAcrossTheSubModule:
    def test_finance_every_form_matches_its_pinned_field_whitelist(self):
        """A field added to (or dropped from) any 4.18 form is a FAILURE, not a silent change.

        All three are ``Meta.fields`` whitelists rather than ``Meta.exclude``: a whitelist fails
        CLOSED when a column is added to the model later, which is exactly what stops a system column
        becoming user-editable by accident.
        """
        for name, form in _finance_unbound_forms().items():
            assert list(form.fields) == _finance_EXPECTED_FIELDS[name], name

    def test_finance_no_form_exposes_tenant_or_the_auto_number(self):
        """``tenant`` is stamped by ``crud_create`` (and, on the tariff, by ``TenantUniqueMixin``
        BEFORE validation); the numbers are minted in ``TenantNumbered.save()``. Either on a form is
        a mass-assignment hole."""
        for name, form in _finance_unbound_forms().items():
            assert "tenant" not in form.fields, name
            assert "number" not in form.fields, name

    def test_finance_no_form_exposes_a_workflow_or_derived_column(self):
        """``status`` belongs to the verb ladder, ``bill`` to ``draft_bill()``, and the five money
        columns to ``recalc_totals()``. A typed total would be a second, un-auditable answer to what
        it cost to land these goods."""
        for name, form in _finance_unbound_forms().items():
            for field_name in _finance_FORBIDDEN_FIELDS:
                assert field_name not in form.fields, f"{name}.{field_name}"

    def test_finance_no_form_exposes_a_secret_or_credential_field(self):
        """L20. 4.18 stores no API key, token or credential of any kind, and no form may render one."""
        for name, form in _finance_unbound_forms().items():
            for field_name in form.fields:
                lowered = field_name.lower()
                for token in _finance_SECRET_TOKENS:
                    assert token not in lowered, f"{name}.{field_name} looks like a secret"

    def test_finance_no_form_exposes_a_system_timestamp(self):
        """L22. A ``DateTimeField`` on a form's ``DateInput`` is silently TRUNCATED to midnight, so
        every system ``*_at`` column stays ``editable=False`` and off every form — ``accrued_at``
        above all, since it is the evidence of when the accrual was raised."""
        for name, form in _finance_unbound_forms().items():
            for field_name in form.fields:
                assert not field_name.endswith("_at"), f"{name}.{field_name}"

    def test_finance_no_form_exposes_a_derived_property(self):
        """``is_current``, ``is_editable``, ``allocatable_amount``, ``effective_basis`` and
        ``capitalises`` are computed reads, never columns — a form field of that name would be a
        stored second answer that goes stale by sitting still (L29)."""
        for name, form in _finance_unbound_forms().items():
            for field_name in ("is_current", "is_editable", "allocatable_amount",
                               "effective_basis", "capitalises", "variance_amount"):
                assert field_name not in form.fields, f"{name}.{field_name}"

    def test_finance_a_tenantless_caller_is_offered_nothing(self):
        """The superuser has ``tenant=None`` BY DESIGN. Every tenant-scoped dropdown must fall to
        EMPTY rather than to the unscoped default manager, which would pool every workspace's rows
        into one ``<select>``."""
        for name, form in _finance_unbound_forms(tenant=None).items():
            for field_name, field in form.fields.items():
                if not isinstance(field, django_forms.ModelChoiceField):
                    continue
                if field.queryset.model.__name__ == "Currency":
                    continue  # GLOBAL master — no tenant column to scope by
                assert not field.queryset.exists(), f"{name}.{field_name} leaked rows"

    def test_finance_no_tenant_a_dropdown_contains_a_tenant_b_row(
            self, tenant_a, tenant_b, finance_receipt_b, supplier_b, shipment_b, trade_document_b,
            freight_invoice_b, gl_expense_b, finance_tax_code_b, finance_duty_tariff_b):
        """The mandatory isolation assertion at the FORM boundary: every ModelChoiceField offered to
        tenant A is empty of tenant B rows, for all three forms at once."""
        for name, form in _finance_unbound_forms(tenant=tenant_a).items():
            for field_name, field in form.fields.items():
                if not isinstance(field, django_forms.ModelChoiceField):
                    continue
                if field.queryset.model.__name__ == "Currency":
                    continue  # GLOBAL master
                foreign = [row.pk for row in field.queryset
                           if getattr(row, "tenant_id", None) != tenant_a.pk]
                assert not foreign, f"{name}.{field_name} offered tenant_b rows {foreign}"


# =================================================================================================
# DutyTariffForm — shape
# =================================================================================================
class TestFinanceDutyTariffFormShape:
    def test_finance_dutytariff_form_carries_exactly_the_eight_editable_columns(self):
        from apps.scm.forms import DutyTariffForm
        assert list(DutyTariffForm(tenant=None).fields) == \
            _finance_EXPECTED_FIELDS["DutyTariffForm"]

    def test_finance_dutytariff_form_excludes_tenant_number_and_the_timestamps(self):
        """The model has no other columns, so this list is the WHOLE non-editable surface."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(tenant=None)
        for field_name in ("tenant", "number", "created_at", "updated_at"):
            assert field_name not in form.fields

    def test_finance_dutytariff_form_keeps_is_active_on_the_form_deliberately(self):
        """``is_active`` is STAFF CONFIGURATION — retiring a rate without losing what it costed —
        not a workflow status. Asserted so it cannot be "tidied away" to match a sibling model whose
        status column belongs to a verb ladder."""
        from apps.scm.forms import DutyTariffForm
        assert "is_active" in DutyTariffForm(tenant=None).fields

    def test_finance_dutytariff_form_states_the_two_instructions_to_the_typist(self):
        """Set on the FORM rather than the model because they read as instructions rather than as
        definitions — most of all on ``effective_from``, where "required" is a design decision (a
        NULL member silently disables the unique key in MySQL), not a fact about duty schedules."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(tenant=None)
        assert form.fields["country_of_origin"].help_text == \
            "Leave blank to apply to any country of origin."
        assert "cannot be looked up by transaction date" in form.fields["effective_from"].help_text

    def test_finance_dutytariff_form_mixes_in_the_tenant_unique_guard(self):
        """``TenantUniqueMixin`` is LOAD-BEARING: Django skips a ``unique_together`` entirely when any
        member field is excluded from validation, and ``tenant`` is never a form field. Without the
        mixin an everyday duplicate is an uncaught ``IntegrityError`` — a 500 on a mainline CRUD
        path."""
        from apps.scm.forms._common import TenantUniqueMixin
        from apps.scm.forms import DutyTariffForm
        assert issubclass(DutyTariffForm, TenantUniqueMixin)


# =================================================================================================
# DutyTariffForm — validation
# =================================================================================================
class TestFinanceDutyTariffFormValidation:
    def test_finance_dutytariff_form_accepts_a_minimal_valid_post(self, tenant_a):
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(data=_finance_tariff_post(timezone.localdate()), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_finance_dutytariff_form_requires_hs_code_rate_and_start_date(self, tenant_a):
        """Three required boxes. ``effective_from`` is required because a rate with no start date
        cannot be windowed by transaction date at all."""
        from apps.scm.forms import DutyTariffForm
        data = _finance_tariff_post(timezone.localdate(), hs_code="", duty_rate_pct="")
        data["effective_from"] = ""
        form = DutyTariffForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert set(form.errors) == {"hs_code", "duty_rate_pct", "effective_from"}

    def test_finance_dutytariff_form_leaves_origin_description_and_window_optional(self, tenant_a):
        """A blank origin MEANS "any origin" — it is the catch-all row, not a missing answer."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(timezone.localdate(), country_of_origin="", description="",
                                      effective_to="", tax_code=""),
            tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_finance_dutytariff_form_refuses_an_inverted_effective_window(self, tenant_a):
        """The pinned sentence, keyed on ``effective_to`` — a key the FORM carries, so it renders as
        a field error instead of raising ``ValueError`` out of ``add_error``."""
        from apps.scm.forms import DutyTariffForm
        today = timezone.localdate()
        form = DutyTariffForm(
            data=_finance_tariff_post(today, effective_to=(today - datetime.timedelta(days=1))
                                      .isoformat()),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "effective_to" in form.errors
        assert "would stop applying" in _finance_errors_text(form)
        assert "before it starts" in _finance_errors_text(form)

    def test_finance_dutytariff_form_accepts_a_window_that_ends_on_its_start_day(self, tenant_a):
        """A one-day rate is legal — the guard is ``<``, not ``<=``."""
        from apps.scm.forms import DutyTariffForm
        today = timezone.localdate()
        form = DutyTariffForm(data=_finance_tariff_post(today, effective_to=today.isoformat()),
                              tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_finance_dutytariff_form_upper_cases_and_strips_the_hs_code(self, tenant_a):
        """Normalisation lives in the MODEL's ``clean()`` because ``hs_code`` is a member of the
        natural key and ``full_clean()`` runs ``clean()`` BEFORE ``validate_unique()``."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(timezone.localdate(), hs_code="  ab8471.30  ",
                                      country_of_origin="  Japan  "),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.hs_code == "AB8471.30"
        assert obj.country_of_origin == "Japan"

    def test_finance_dutytariff_form_stamps_the_tenant_before_validation(self, tenant_a):
        """``TenantUniqueMixin.__init__`` puts the workspace on the instance BEFORE ``is_valid()``,
        which is what makes the uniqueness check run against a real tenant rather than ``None`` —
        and what makes the model's own cross-tenant leg live on the CREATE path."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(data=_finance_tariff_post(timezone.localdate()), tenant=tenant_a)
        assert form.instance.tenant_id == tenant_a.pk

    def test_finance_dutytariff_form_mints_the_number_on_save_never_from_the_body(self, tenant_a):
        """A ``number`` key in the body is ignored — the field is not on the form, and
        ``TenantNumbered.save()`` mints ``DTY-#####``."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(timezone.localdate(), number="DTY-99999"), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.number.startswith("DTY-")
        assert obj.number != "DTY-99999"

    def test_finance_dutytariff_form_refuses_a_duplicate_natural_key(
            self, tenant_a, finance_duty_tariff_a):
        """Re-entering an HS code / origin / start date that already exists is THE ordinary mistake
        on this page. Without ``TenantUniqueMixin`` it sails through ``is_valid()`` and 500s on
        ``.save()``; here it must come back as a rendered form error."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(finance_duty_tariff_a.effective_from,
                                      hs_code=finance_duty_tariff_a.hs_code,
                                      country_of_origin=finance_duty_tariff_a.country_of_origin),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "already exists" in _finance_errors_text(form)

    def test_finance_dutytariff_form_catches_a_duplicate_hidden_by_whitespace_and_case(
            self, tenant_a, finance_duty_tariff_a):
        """``  8471.30  `` and ``8471.30`` are the SAME classification. Normalising in ``clean()`` is
        what makes them collide on the uniqueness check instead of quietly becoming two rows that
        ``rate_for()`` then has to choose between."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(finance_duty_tariff_a.effective_from,
                                      hs_code="  8471.30  ",
                                      country_of_origin="  Germany  "),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "already exists" in _finance_errors_text(form)

    def test_finance_dutytariff_form_allows_a_second_origin_on_the_same_day(
            self, tenant_a, finance_duty_tariff_a):
        """The natural key includes the origin, so the any-origin fallback and an origin-specific
        rate may legally start on the same day — that coexistence is what ``rate_for()``'s ordering
        exists to resolve."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(finance_duty_tariff_a.effective_from,
                                      hs_code=finance_duty_tariff_a.hs_code,
                                      country_of_origin=""),
            tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_finance_dutytariff_form_does_not_flag_a_row_as_its_own_duplicate(
            self, tenant_a, finance_duty_tariff_a):
        """The EDIT path re-posts the row's own natural key; ``validate_unique`` must exclude the
        instance itself or every edit would be refused."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(finance_duty_tariff_a.effective_from,
                                      hs_code=finance_duty_tariff_a.hs_code,
                                      country_of_origin=finance_duty_tariff_a.country_of_origin,
                                      duty_rate_pct="7.250"),
            instance=finance_duty_tariff_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("7.250")

    def test_finance_dutytariff_form_lets_a_duplicate_of_ANOTHER_workspace_through(
            self, tenant_a, finance_duty_tariff_b):
        """The constraint is per-workspace. Two tenants owing the same duty on the same code is the
        normal case, not a clash."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(finance_duty_tariff_b.effective_from,
                                      hs_code=finance_duty_tariff_b.hs_code,
                                      country_of_origin=finance_duty_tariff_b.country_of_origin),
            tenant=tenant_a)
        assert form.is_valid(), form.errors

    @pytest.mark.parametrize("rate", ["-1.000", "NaN", "Infinity", "-Infinity", "abc",
                                      "150.000", "9999.999"])
    def test_finance_dutytariff_form_refuses_a_junk_or_out_of_range_rate(self, tenant_a, rate):
        """Negative, non-finite, non-numeric, over 100 % and over ``max_digits=6`` all come back as
        FIELD ERRORS. Any of them reaching the DB layer is a 500 on a mainline CRUD path."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(timezone.localdate(), duty_rate_pct=rate), tenant=tenant_a)
        assert not form.is_valid()
        assert "duty_rate_pct" in form.errors

    def test_finance_dutytariff_form_accepts_the_boundary_rates_zero_and_one_hundred(self, tenant_a):
        """The validators are ``Min(0)`` / ``Max(100)`` — both endpoints are legal, and a free-trade
        agreement really does produce a 0.000 % line."""
        from apps.scm.forms import DutyTariffForm
        today = timezone.localdate()
        for rate in ("0.000", "100.000"):
            form = DutyTariffForm(
                data=_finance_tariff_post(today, duty_rate_pct=rate,
                                          country_of_origin=f"Origin {rate}"),
                tenant=tenant_a)
            assert form.is_valid(), (rate, form.errors)

    def test_finance_dutytariff_form_refuses_a_junk_effective_date(self, tenant_a):
        from apps.scm.forms import DutyTariffForm
        data = _finance_tariff_post(timezone.localdate())
        data["effective_from"] = "not-a-date"
        form = DutyTariffForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "effective_from" in form.errors

    def test_finance_dutytariff_form_refuses_an_over_length_hs_code(self, tenant_a):
        """``max_length=20``. A silently truncated classification is a wrong duty rate."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(timezone.localdate(), hs_code="8" * 21), tenant=tenant_a)
        assert not form.is_valid()
        assert "hs_code" in form.errors


# =================================================================================================
# DutyTariffForm — FK scoping
# =================================================================================================
class TestFinanceDutyTariffFormQuerysets:
    def test_finance_dutytariff_tax_code_dropdown_is_tenant_scoped(
            self, tenant_a, finance_tax_code_a, finance_tax_code_b):
        from apps.scm.forms import DutyTariffForm
        offered = list(DutyTariffForm(tenant=tenant_a).fields["tax_code"].queryset)
        assert finance_tax_code_a in offered
        assert finance_tax_code_b not in offered

    def test_finance_dutytariff_tax_code_dropdown_hides_a_retired_code(
            self, tenant_a, finance_tax_code_a):
        """The narrowing is ``is_active=True`` — a retired rate is not one anybody should newly pick."""
        from apps.scm.forms import DutyTariffForm
        finance_tax_code_a.is_active = False
        finance_tax_code_a.save(update_fields=["is_active"])
        assert not DutyTariffForm(tenant=tenant_a).fields["tax_code"].queryset.exists()

    def test_finance_dutytariff_edit_form_re_admits_a_deactivated_stored_tax_code(
            self, tenant_a, _finance_tariff_with_tax_code_a, finance_tax_code_a):
        """``_keep_current``. Without it the stored option vanishes, the browser posts an empty value,
        and somebody fixing a typo in the description silently NULLs the link."""
        from apps.scm.forms import DutyTariffForm
        finance_tax_code_a.is_active = False
        finance_tax_code_a.save(update_fields=["is_active"])
        form = DutyTariffForm(instance=_finance_tariff_with_tax_code_a, tenant=tenant_a)
        assert finance_tax_code_a in list(form.fields["tax_code"].queryset)

    def test_finance_dutytariff_edit_form_re_admission_stays_inside_the_workspace(
            self, tenant_a, _finance_tariff_with_tax_code_a, finance_tax_code_b):
        """``_keep_current``'s base queryset is TENANT-SCOPED, so the union can only ever re-admit
        this workspace's own row — never a foreign one that somehow reached the column."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(instance=_finance_tariff_with_tax_code_a, tenant=tenant_a)
        assert finance_tax_code_b not in list(form.fields["tax_code"].queryset)

    def test_finance_dutytariff_form_rejects_a_foreign_tax_code_pk(
            self, tenant_a, finance_tax_code_b):
        """A crafted POST naming another workspace's tax code is a rendered FIELD error on
        ``tax_code`` — 200 with errors, never an ``IntegrityError`` and never a 500."""
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(timezone.localdate(), tax_code=finance_tax_code_b.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "tax_code" in form.errors

    def test_finance_dutytariff_clean_rejects_a_foreign_tax_code_even_unnarrowed(
            self, tenant_a, finance_tax_code_b):
        """The SECOND boundary, on its own. Widening the ``<select>`` (as a later "simplification"
        might) must still be refused by ``_reject_foreign`` with the pinned sentence — a narrowed
        dropdown is UX, never an authorization boundary."""
        from apps.accounting.models import TaxCode
        from apps.scm.forms import DutyTariffForm
        form = DutyTariffForm(
            data=_finance_tariff_post(timezone.localdate(), tax_code=finance_tax_code_b.pk),
            tenant=tenant_a)
        form.fields["tax_code"].queryset = TaxCode.objects.all()
        assert not form.is_valid()
        assert "tax_code" in form.errors
        assert "belongs to another workspace" in _finance_errors_text(form)


# =================================================================================================
# LandedCostVoucherForm — shape
# =================================================================================================
class TestFinanceLandedCostVoucherFormShape:
    def test_finance_voucher_form_carries_the_envelope_only(self):
        from apps.scm.forms import LandedCostVoucherForm
        assert list(LandedCostVoucherForm(tenant=None).fields) == \
            _finance_EXPECTED_FIELDS["LandedCostVoucherForm"]

    def test_finance_voucher_form_carries_no_money_at_all(self):
        """Every figure on a voucher is DERIVED — the totals from its charges by ``recalc_totals()``,
        the allocation from the stock ledger by ``allocate()``. A typed total would be a second,
        un-auditable answer to what it cost to land these goods."""
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(tenant=None)
        for field_name in ("estimated_total", "actual_total", "variance_amount", "variance_pct",
                           "allocated_total", "amount", "total"):
            assert field_name not in form.fields

    def test_finance_voucher_form_excludes_the_status_ladder_and_the_bill_handoff(self):
        """``status`` moves only along ``allocate() → accrue() → draft_bill()`` (plus ``cancel()``),
        and ``bill`` is written by ``draft_bill()`` alone."""
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(tenant=None)
        assert "status" not in form.fields
        assert "bill" not in form.fields

    def test_finance_voucher_form_excludes_the_accrual_timestamp(self):
        """L22 in its sharpest form: ``accrued_at`` is a ``DateTimeField``, and a ``DateInput`` would
        truncate its time half on the next save."""
        from apps.scm.forms import LandedCostVoucherForm
        assert "accrued_at" not in LandedCostVoucherForm(tenant=None).fields

    def test_finance_voucher_form_does_not_mix_in_the_tenant_unique_guard(self):
        """Deliberately NOT mixed in, unlike ``DutyTariffForm``: the only ``unique_together`` here is
        ``("tenant", "number")`` and ``number`` is auto-assigned, so there is no user-enterable
        duplicate for the mixin to catch. Adding it would imply a check that does nothing."""
        from apps.scm.forms._common import TenantUniqueMixin
        from apps.scm.forms import LandedCostVoucherForm
        assert not issubclass(LandedCostVoucherForm, TenantUniqueMixin)


# =================================================================================================
# LandedCostVoucherForm — validation
# =================================================================================================
class TestFinanceLandedCostVoucherFormValidation:
    def test_finance_voucher_form_accepts_a_minimal_valid_post(
            self, tenant_a, finance_receipt_a, supplier_a):
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(
            data=_finance_voucher_post(finance_receipt_a.pk, supplier_a.pk, timezone.localdate()),
            tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_finance_voucher_form_requires_receipt_party_and_cost_date(self, tenant_a):
        """All three are non-null on the model, and the payee's requirement comes from downstream:
        ``accounting.Bill.party`` is PROTECT and non-null, so a voucher with no payee could never
        draft the bill it exists to draft."""
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(
            data={"goods_receipt": "", "party": "", "cost_date": "", "allocation_basis": "value"},
            tenant=tenant_a)
        assert not form.is_valid()
        assert {"goods_receipt", "party", "cost_date"} <= set(form.errors)

    def test_finance_voucher_form_leaves_shipment_document_currency_and_notes_optional(
            self, tenant_a, finance_receipt_a, supplier_a):
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(
            data=_finance_voucher_post(finance_receipt_a.pk, supplier_a.pk, timezone.localdate(),
                                       shipment="", trade_document="", currency="", notes=""),
            tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_finance_voucher_form_offers_exactly_five_allocation_bases(self):
        """FIVE, and there is deliberately no ``manual`` sixth — a hand-typed per-row split needs an
        editable grid over rows that are ``editable=False`` by construction."""
        from apps.scm.forms import LandedCostVoucherForm
        values = _finance_choice_values(LandedCostVoucherForm(tenant=None), "allocation_basis")
        assert values == ["value", "quantity", "weight", "volume", "equal"]

    def test_finance_voucher_form_refuses_an_unknown_allocation_basis(
            self, tenant_a, finance_receipt_a, supplier_a):
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(
            data=_finance_voucher_post(finance_receipt_a.pk, supplier_a.pk, timezone.localdate(),
                                       allocation_basis="manual"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "allocation_basis" in form.errors

    def test_finance_voucher_form_refuses_a_junk_cost_date(
            self, tenant_a, finance_receipt_a, supplier_a):
        from apps.scm.forms import LandedCostVoucherForm
        data = _finance_voucher_post(finance_receipt_a.pk, supplier_a.pk, timezone.localdate())
        data["cost_date"] = "not-a-date"
        form = LandedCostVoucherForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "cost_date" in form.errors

    def test_finance_voucher_form_ignores_a_status_or_total_smuggled_into_the_body(
            self, tenant_a, finance_receipt_a, supplier_a):
        """Mass assignment: keys for columns that are not on the form must be dropped, not applied."""
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(
            data=_finance_voucher_post(finance_receipt_a.pk, supplier_a.pk, timezone.localdate(),
                                       status="reconciled", allocated_total="9999.00",
                                       actual_total="9999.00", number="LC-99999"),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.instance
        assert obj.status == "draft"
        assert obj.allocated_total == Decimal("0")
        assert obj.actual_total == Decimal("0")
        assert obj.number in ("", None)


# =================================================================================================
# LandedCostVoucherForm — FK scoping
# =================================================================================================
class TestFinanceLandedCostVoucherFormQuerysets:
    def test_finance_voucher_form_offers_received_receipts_only(
            self, tenant_a, finance_receipt_a, goods_receipt_a):
        """A DRAFT GRN has posted nothing to the stock ledger, so a voucher against one could be
        created and then never allocated — offering it is offering a dead end."""
        from apps.scm.forms import LandedCostVoucherForm
        offered = list(LandedCostVoucherForm(tenant=tenant_a).fields["goods_receipt"].queryset)
        assert finance_receipt_a in offered
        assert goods_receipt_a not in offered

    def test_finance_voucher_form_refuses_a_draft_receipt_posted_by_hand(
            self, tenant_a, goods_receipt_a, supplier_a):
        """The narrowed ``<select>`` and the bound field agree — a draft GRN pk in the body is a
        field error, not a saved dead end."""
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(
            data=_finance_voucher_post(goods_receipt_a.pk, supplier_a.pk, timezone.localdate()),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "goods_receipt" in form.errors

    def test_finance_voucher_form_offers_only_carrier_roled_parties(
            self, tenant_a, supplier_a, vendor_a, carrier_party_a, customer_a,
            non_supplier_party_a):
        """``_carrier_parties`` — supplier / vendor / partner. A forwarder or customs broker is
        procured from exactly the way a carrier is; a customer is not a payee."""
        from apps.scm.forms import LandedCostVoucherForm
        offered = list(LandedCostVoucherForm(tenant=tenant_a).fields["party"].queryset)
        assert supplier_a in offered
        assert vendor_a in offered
        assert carrier_party_a in offered
        assert customer_a not in offered
        assert non_supplier_party_a not in offered

    def test_finance_voucher_form_refuses_a_party_with_no_buy_from_role(
            self, tenant_a, finance_receipt_a, customer_a):
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(
            data=_finance_voucher_post(finance_receipt_a.pk, customer_a.pk, timezone.localdate()),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "party" in form.errors

    def test_finance_voucher_form_scopes_shipment_and_trade_document_to_the_workspace(
            self, tenant_a, shipment_a, shipment_b, trade_document_a, trade_document_b):
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(tenant=tenant_a)
        shipments = list(form.fields["shipment"].queryset)
        documents = list(form.fields["trade_document"].queryset)
        assert shipment_a in shipments and shipment_b not in shipments
        assert trade_document_a in documents and trade_document_b not in documents

    def test_finance_voucher_form_never_tenant_filters_the_global_currency(
            self, tenant_a, usd, _finance_inactive_currency):
        """``accounting.Currency`` is GLOBAL — no tenant column — so filtering it by tenant would
        empty the dropdown. The only legal narrowing is ``is_active``."""
        from apps.scm.forms import LandedCostVoucherForm
        offered = list(LandedCostVoucherForm(tenant=tenant_a).fields["currency"].queryset)
        assert usd in offered
        assert _finance_inactive_currency not in offered

    def test_finance_voucher_form_offers_a_tenantless_caller_nothing(
            self, finance_receipt_a, supplier_a, shipment_a, trade_document_a):
        """``.none()`` for every one of the four tenant-scoped dropdowns, rather than the unscoped
        default manager that would list every workspace's receipts."""
        from apps.scm.forms import LandedCostVoucherForm
        form = LandedCostVoucherForm(tenant=None)
        for field_name in ("goods_receipt", "party", "shipment", "trade_document"):
            assert not form.fields[field_name].queryset.exists(), field_name

    @pytest.mark.parametrize("field_name", ["goods_receipt", "party", "shipment", "trade_document"])
    def test_finance_voucher_form_rejects_every_foreign_fk_pk(
            self, tenant_a, finance_receipt_a, supplier_a, finance_receipt_b, supplier_b,
            shipment_b, trade_document_b, field_name):
        """A crafted POST naming another workspace's receipt, payee, shipment or document is a
        rendered field error on THAT field — never a saved cross-tenant pointer."""
        from apps.scm.forms import LandedCostVoucherForm
        foreign = {"goods_receipt": finance_receipt_b, "party": supplier_b,
                   "shipment": shipment_b, "trade_document": trade_document_b}[field_name]
        form = LandedCostVoucherForm(
            data=_finance_voucher_post(finance_receipt_a.pk, supplier_a.pk, timezone.localdate(),
                                       **{field_name: foreign.pk}),
            tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors

    @pytest.mark.parametrize("field_name", ["goods_receipt", "party", "shipment", "trade_document"])
    def test_finance_voucher_clean_rejects_a_foreign_fk_even_unnarrowed(
            self, tenant_a, finance_receipt_a, supplier_a, finance_receipt_b, supplier_b,
            shipment_b, trade_document_b, field_name):
        """The ``_reject_foreign`` boundary on its own, with the narrowing widened out from under it.

        ``party`` is in the FORM's tuple even though the MODEL's ``TENANT_SCOPED_FKS`` omits it — a
        foreign payee is exactly what would put another workspace's party onto a drafted
        ``accounting.Bill``.
        """
        from apps.core.models import Party
        from apps.scm.forms import LandedCostVoucherForm
        from apps.scm.models import GoodsReceiptNote, Shipment, TradeDocument
        foreign = {"goods_receipt": finance_receipt_b, "party": supplier_b,
                   "shipment": shipment_b, "trade_document": trade_document_b}[field_name]
        widened = {"goods_receipt": GoodsReceiptNote.objects.all(), "party": Party.objects.all(),
                   "shipment": Shipment.objects.all(),
                   "trade_document": TradeDocument.objects.all()}[field_name]
        form = LandedCostVoucherForm(
            data=_finance_voucher_post(finance_receipt_a.pk, supplier_a.pk, timezone.localdate(),
                                       **{field_name: foreign.pk}),
            tenant=tenant_a)
        form.fields[field_name].queryset = widened
        assert not form.is_valid()
        assert field_name in form.errors
        assert "belongs to another workspace" in _finance_errors_text(form)


# =================================================================================================
# LandedCostChargeForm — shape (the parent comes from the ROUTE)
# =================================================================================================
class TestFinanceLandedCostChargeFormShape:
    def test_finance_charge_form_carries_the_fourteen_cost_line_columns(self):
        from apps.scm.forms import LandedCostChargeForm
        assert list(LandedCostChargeForm(tenant=None, voucher=None).fields) == \
            _finance_EXPECTED_FIELDS["LandedCostChargeForm"]

    def test_finance_charge_form_excludes_the_parent_voucher(self):
        """THE exclusion, and it is a SECURITY decision rather than a tidiness one: a parent pk in a
        POST body is how a caller grafts a charge onto another workspace's voucher."""
        from apps.scm.forms import LandedCostChargeForm
        assert "voucher" not in LandedCostChargeForm(tenant=None, voucher=None).fields

    def test_finance_charge_form_takes_its_parent_from_the_route(self, tenant_a, finance_voucher_a):
        """Assigned in ``__init__`` — BEFORE validation — so ``full_clean()`` on the unsaved instance
        has a voucher to read and the view never depends on POST for the column that decides which
        voucher owns the charge."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(tenant=tenant_a, voucher=finance_voucher_a)
        assert form.voucher == finance_voucher_a
        assert form.instance.voucher_id == finance_voucher_a.pk

    def test_finance_charge_form_ignores_a_voucher_pk_smuggled_into_the_body(
            self, tenant_a, finance_voucher_a, finance_voucher_b):
        """The route's parent WINS. A ``voucher`` key naming tenant_b's voucher is not a field, so it
        is dropped — the saved charge still belongs to the voucher the URL resolved."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(voucher=finance_voucher_b.pk),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        charge = form.save()
        assert charge.voucher_id == finance_voucher_a.pk

    def test_finance_charge_form_has_no_tenant_number_or_timestamp_to_exclude(self):
        """``LandedCostCharge`` is a TENANT-LESS child (the ``BillLine`` / ``GoodsReceiptLine``
        convention) with no number and no ``*_at`` columns — a second ``tenant`` FK here would be a
        second answer to "whose row is this"."""
        from apps.scm.models import LandedCostCharge
        columns = {field.name for field in LandedCostCharge._meta.fields}
        assert "tenant" not in columns
        assert "number" not in columns
        assert not any(name.endswith("_at") for name in columns)

    def test_finance_charge_form_keeps_the_two_capitalisation_switches_on_the_form(self):
        """``is_recoverable`` and ``capitalise_to_inventory`` are decisions a human makes per line —
        together they are what ``capitalises`` computes from, and recoverable tax NEVER lands on the
        units."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(tenant=None, voucher=None)
        assert "is_recoverable" in form.fields
        assert "capitalise_to_inventory" in form.fields


# =================================================================================================
# LandedCostChargeForm — validation
# =================================================================================================
class TestFinanceLandedCostChargeFormValidation:
    def test_finance_charge_form_accepts_a_minimal_valid_post(self, tenant_a, finance_voucher_a):
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(data=_finance_charge_post(), tenant=tenant_a,
                                    voucher=finance_voucher_a)
        assert form.is_valid(), form.errors

    def test_finance_charge_form_offers_eleven_charge_types(self):
        """Wider than the 4.6 freight vocabulary on purpose: a landed cost sheet carries the customs
        and terminal side of the bill, which a carrier's own invoice never does."""
        from apps.scm.forms import LandedCostChargeForm
        values = _finance_choice_values(LandedCostChargeForm(tenant=None, voucher=None),
                                        "charge_type")
        assert values == ["freight", "duty", "brokerage", "insurance", "handling", "drayage",
                          "port_fees", "fuel_surcharge", "inspection", "storage", "other"]

    def test_finance_charge_form_refuses_an_unknown_charge_type(self, tenant_a, finance_voucher_a):
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(data=_finance_charge_post(charge_type="banana"),
                                    tenant=tenant_a, voucher=finance_voucher_a)
        assert not form.is_valid()
        assert "charge_type" in form.errors

    def test_finance_charge_form_prepends_the_inherit_option_to_the_basis(self):
        """Blank MEANS "inherit the voucher's", so the empty option SAYS so rather than showing the
        anonymous ``---------`` a reader has to guess at."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(tenant=None, voucher=None)
        choices = list(form.fields["allocation_basis"].choices)
        assert choices[0][0] == ""
        assert "Inherit the voucher's basis" in str(choices[0][1])
        assert [value for value, _ in choices[1:]] == \
            ["value", "quantity", "weight", "volume", "equal"]

    def test_finance_charge_form_allocation_basis_is_optional(self, tenant_a, finance_voucher_a):
        """``required=False`` is what LETS it be blank — and a blank basis is the common case."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(data=_finance_charge_post(allocation_basis=""),
                                    tenant=tenant_a, voucher=finance_voucher_a)
        assert form.fields["allocation_basis"].required is False
        assert form.is_valid(), form.errors
        assert form.save().allocation_basis == ""

    def test_finance_charge_form_blank_basis_inherits_the_vouchers(self, tenant_a,
                                                                   finance_voucher_a):
        """The stored value stays blank; ``effective_basis`` is what resolves it — the inheritance is
        computed, never copied (a copy would go stale the moment the voucher's basis changed)."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(data=_finance_charge_post(allocation_basis=""),
                                    tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        charge = form.save()
        assert charge.allocation_basis == ""
        assert charge.effective_basis == finance_voucher_a.allocation_basis

    def test_finance_charge_form_treats_a_blank_duty_rate_as_zero(self, tenant_a,
                                                                  finance_voucher_a):
        """``required=False`` alone would hand a NOT NULL column ``None``; ``clean_duty_rate_pct``
        is the other half and is NOT optional. A cleared box means "no duty", not "invalid"."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(data=_finance_charge_post(duty_rate_pct=""),
                                    tenant=tenant_a, voucher=finance_voucher_a)
        assert form.fields["duty_rate_pct"].required is False
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("0")

    def test_finance_charge_form_refuses_a_duty_rate_on_a_non_duty_charge(
            self, tenant_a, finance_voucher_a):
        """Keyed on ``duty_rate_pct``, a field the FORM carries — a model error keyed on a column the
        form lacks raises ``ValueError`` out of ``add_error``, i.e. a 500 instead of a field error."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="freight", duty_rate_pct="2.500"),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert not form.is_valid()
        assert "duty_rate_pct" in form.errors
        assert "duty rate belongs on a customs duty charge" in _finance_errors_text(form)

    def test_finance_charge_form_accepts_a_duty_rate_on_a_duty_charge(self, tenant_a,
                                                                      finance_voucher_a):
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", duty_rate_pct="2.500"),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("2.500")

    @pytest.mark.parametrize("amount", ["-1.00", "NaN", "Infinity", "-Infinity", "abc",
                                        "999999999999999.00"])
    def test_finance_charge_form_refuses_a_junk_estimated_amount(
            self, tenant_a, finance_voucher_a, amount):
        """Negative, non-finite, non-numeric and over-``max_digits=14`` all come back as a FIELD
        error. A ``NaN`` reaching the allocation arithmetic would poison every derived total."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(data=_finance_charge_post(estimated_amount=amount),
                                    tenant=tenant_a, voucher=finance_voucher_a)
        assert not form.is_valid()
        assert "estimated_amount" in form.errors

    @pytest.mark.parametrize("amount", ["-0.01", "NaN", "Infinity", "nonsense"])
    def test_finance_charge_form_refuses_a_junk_actual_amount(
            self, tenant_a, finance_voucher_a, amount):
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(data=_finance_charge_post(actual_amount=amount),
                                    tenant=tenant_a, voucher=finance_voucher_a)
        assert not form.is_valid()
        assert "actual_amount" in form.errors

    def test_finance_charge_form_accepts_zero_on_both_amounts(self, tenant_a, finance_voucher_a):
        """A charge that is known about but not yet priced is legal — it simply allocates nothing."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(estimated_amount="0.00", actual_amount="0.00"),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().allocatable_amount == Decimal("0")

    def test_finance_charge_form_refuses_a_duty_rate_over_one_hundred_percent(
            self, tenant_a, finance_voucher_a):
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", duty_rate_pct="150.000"),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert not form.is_valid()
        assert "duty_rate_pct" in form.errors

    def test_finance_charge_form_leaves_description_and_every_fk_optional(
            self, tenant_a, finance_voucher_a):
        """Only the choice columns and the two amounts carry defaults; nothing else is mandatory, so
        a broker's one-line "handling 40.00" is enterable without inventing an account."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(description="", party="", freight_invoice="", gl_account="",
                                      tax_code="", hs_code="", country_of_origin=""),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors

    def test_finance_charge_form_defaults_the_two_switches_from_the_body(
            self, tenant_a, finance_voucher_a):
        """An absent checkbox reads as UNCHECKED — ``is_recoverable`` is omitted from the payload and
        must land False, ``capitalise_to_inventory`` is posted and must land True."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(data=_finance_charge_post(), tenant=tenant_a,
                                    voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        charge = form.save()
        assert charge.is_recoverable is False
        assert charge.capitalise_to_inventory is True
        assert charge.capitalises is True


# =================================================================================================
# LandedCostChargeForm — the DutyTariff.rate_for() defaulting (the request-path integration)
# =================================================================================================
class TestFinanceLandedCostChargeFormRateDefaulting:
    def test_finance_charge_form_defaults_the_duty_rate_from_the_tariff(
            self, tenant_a, finance_voucher_a, finance_duty_tariff_a):
        """Without this the Tax Management master feeds nothing at runtime and the help text
        ("Snapshotted from the duty tariff") is a promise nothing keeps."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", hs_code="8471.30",
                                      country_of_origin="Germany", duty_rate_pct=""),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("2.500")

    def test_finance_charge_form_prefers_the_named_origin_over_the_any_origin_row(
            self, tenant_a, finance_voucher_a, finance_duty_tariff_a, finance_duty_tariff_any_a):
        """Both rows legally cover 8471.30 today; the blank-origin one is the FALLBACK, not an
        alternative. Priced differently (2.500 vs 5.000) so the rate alone names the winner."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", hs_code="8471.30",
                                      country_of_origin="Germany", duty_rate_pct=""),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("2.500")

    def test_finance_charge_form_falls_back_to_the_any_origin_rate(
            self, tenant_a, finance_voucher_a, finance_duty_tariff_a, finance_duty_tariff_any_a):
        """An origin with no named rate takes the catch-all row — a blank ``country_of_origin`` on a
        tariff MEANS "any origin", not "unknown"."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", hs_code="8471.30",
                                      country_of_origin="Vietnam", duty_rate_pct=""),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("5.000")

    def test_finance_charge_form_never_overwrites_a_rate_the_typist_stated(
            self, tenant_a, finance_voucher_a, finance_duty_tariff_a):
        """The lookup runs only when the box carries nothing — a broker's entry that disagrees with
        the schedule is the broker's entry, and it is what customs actually applied."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", hs_code="8471.30",
                                      country_of_origin="Germany", duty_rate_pct="9.000"),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("9.000")

    def test_finance_charge_form_leaves_the_rate_alone_when_no_tariff_matches(
            self, tenant_a, finance_voucher_a, finance_duty_tariff_a):
        """``rate_for()`` returns ``None`` rather than raising for anything unresolvable: the caller
        is DEFAULTING a form field, and a missing tariff means "type the rate yourself", not "fail
        the page"."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", hs_code="9999.99",
                                      country_of_origin="Germany", duty_rate_pct=""),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("0")

    def test_finance_charge_form_does_not_default_a_non_duty_charge(
            self, tenant_a, finance_voucher_a, finance_duty_tariff_a):
        """GUARDED ON ``charge_type == "duty"`` and nothing else: ``LandedCostCharge.clean()`` REJECTS
        a non-zero rate on any other type, so defaulting a freight charge that happens to carry an HS
        code would turn a valid line into a validation error the typist cannot see the cause of."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="freight", hs_code="8471.30",
                                      country_of_origin="Germany", duty_rate_pct=""),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("0")

    def test_finance_charge_form_does_not_default_without_an_hs_code(
            self, tenant_a, finance_voucher_a, finance_duty_tariff_any_a):
        """No classification, no lookup — ``rate_for()`` has nothing to match on."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", hs_code="", duty_rate_pct=""),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("0")

    def test_finance_charge_form_never_reads_another_workspaces_duty_schedule(
            self, tenant_a, finance_voucher_a, finance_duty_tariff_b):
        """``rate_for()`` is tenant-scoped: tenant_b's 8528.52 rate must not default a tenant_a
        charge, even though the HS code and origin match exactly."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty",
                                      hs_code=finance_duty_tariff_b.hs_code,
                                      country_of_origin=finance_duty_tariff_b.country_of_origin,
                                      duty_rate_pct=""),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("0")

    def test_finance_charge_form_does_not_default_an_unparented_form(
            self, tenant_a, finance_duty_tariff_a):
        """No voucher means no ``cost_date`` to window the schedule on, and ``rate_for()`` returns
        ``None`` for a missing date rather than reaching for today's."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", hs_code="8471.30",
                                      country_of_origin="Germany", duty_rate_pct=""),
            tenant=tenant_a, voucher=None)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["duty_rate_pct"] == Decimal("0")

    def test_finance_charge_form_ignores_a_retired_tariff(
            self, tenant_a, finance_voucher_a, finance_duty_tariff_a):
        """``is_active=False`` retires a rate without losing what it costed — a retired rate is a
        rate nobody currently owes, so it must not default anything."""
        from apps.scm.forms import LandedCostChargeForm
        finance_duty_tariff_a.is_active = False
        finance_duty_tariff_a.save(update_fields=["is_active"])
        form = LandedCostChargeForm(
            data=_finance_charge_post(charge_type="duty", hs_code="8471.30",
                                      country_of_origin="Germany", duty_rate_pct=""),
            tenant=tenant_a, voucher=finance_voucher_a)
        assert form.is_valid(), form.errors
        assert form.save().duty_rate_pct == Decimal("0")


# =================================================================================================
# LandedCostChargeForm — FK scoping (NOTHING here is scoped automatically)
# =================================================================================================
class TestFinanceLandedCostChargeFormQuerysets:
    def test_finance_charge_form_offers_only_carrier_roled_parties(
            self, tenant_a, finance_voucher_a, supplier_a, customer_a, non_supplier_party_a):
        """``TenantModelForm`` cannot scope anything here — it narrows a ``ModelChoiceField`` only
        when the target's OWN model carries a tenant column AND the form's model reaches its tenant
        directly. ``LandedCostCharge`` reaches its tenant through its parent, so all four FKs are
        narrowed BY HAND."""
        from apps.scm.forms import LandedCostChargeForm
        offered = list(LandedCostChargeForm(tenant=tenant_a,
                                            voucher=finance_voucher_a).fields["party"].queryset)
        assert supplier_a in offered
        assert customer_a not in offered
        assert non_supplier_party_a not in offered

    def test_finance_charge_form_scopes_every_fk_to_the_workspace(
            self, tenant_a, finance_voucher_a, supplier_a, freight_invoice_a, gl_expense,
            finance_tax_code_a, supplier_b, freight_invoice_b, gl_expense_b, finance_tax_code_b):
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(tenant=tenant_a, voucher=finance_voucher_a)
        pairs = {
            "party": (supplier_a, supplier_b),
            "freight_invoice": (freight_invoice_a, freight_invoice_b),
            "gl_account": (gl_expense, gl_expense_b),
            "tax_code": (finance_tax_code_a, finance_tax_code_b),
        }
        for field_name, (mine, theirs) in pairs.items():
            offered = list(form.fields[field_name].queryset)
            assert mine in offered, field_name
            assert theirs not in offered, field_name

    def test_finance_charge_form_hides_a_deactivated_account_or_tax_code(
            self, tenant_a, finance_voucher_a, gl_expense, finance_tax_code_a):
        from apps.scm.forms import LandedCostChargeForm
        gl_expense.is_active = False
        gl_expense.save(update_fields=["is_active"])
        finance_tax_code_a.is_active = False
        finance_tax_code_a.save(update_fields=["is_active"])
        form = LandedCostChargeForm(tenant=tenant_a, voucher=finance_voucher_a)
        assert gl_expense not in list(form.fields["gl_account"].queryset)
        assert finance_tax_code_a not in list(form.fields["tax_code"].queryset)

    def test_finance_charge_edit_form_re_admits_a_deactivated_stored_account(
            self, tenant_a, finance_voucher_a, _finance_charge_with_accounts_a, gl_expense):
        """``_keep_current`` on the account ``draft_bill()`` copies onto the vendor bill line — lost
        by somebody who came to fix a typo in the description, with no error to warn them."""
        from apps.scm.forms import LandedCostChargeForm
        gl_expense.is_active = False
        gl_expense.save(update_fields=["is_active"])
        form = LandedCostChargeForm(instance=_finance_charge_with_accounts_a, tenant=tenant_a,
                                    voucher=finance_voucher_a)
        assert gl_expense in list(form.fields["gl_account"].queryset)

    def test_finance_charge_edit_form_re_admits_a_deactivated_stored_tax_code(
            self, tenant_a, finance_voucher_a, _finance_charge_with_accounts_a,
            finance_tax_code_a):
        from apps.scm.forms import LandedCostChargeForm
        finance_tax_code_a.is_active = False
        finance_tax_code_a.save(update_fields=["is_active"])
        form = LandedCostChargeForm(instance=_finance_charge_with_accounts_a, tenant=tenant_a,
                                    voucher=finance_voucher_a)
        assert finance_tax_code_a in list(form.fields["tax_code"].queryset)

    def test_finance_charge_edit_form_re_admits_a_party_whose_role_was_removed(
            self, tenant_a, finance_voucher_a, _finance_charge_with_accounts_a, supplier_a):
        """The role-narrowed queryset ends in ``.distinct()``; ``_keep_current`` is written as one
        ``filter(Q | Q)`` over a ``pk__in`` subquery precisely because OR-ing a distinct queryset
        raises ``TypeError`` — a live 500 on the EDIT path only."""
        from apps.scm.forms import LandedCostChargeForm
        supplier_a.roles.all().delete()
        form = LandedCostChargeForm(instance=_finance_charge_with_accounts_a, tenant=tenant_a,
                                    voucher=finance_voucher_a)
        assert supplier_a in list(form.fields["party"].queryset)

    def test_finance_charge_edit_form_re_admission_stays_inside_the_workspace(
            self, tenant_a, finance_voucher_a, _finance_charge_with_accounts_a, gl_expense_b,
            finance_tax_code_b, supplier_b):
        """Every ``_keep_current`` base here is TENANT-SCOPED, so no union can re-admit a foreign
        row."""
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(instance=_finance_charge_with_accounts_a, tenant=tenant_a,
                                    voucher=finance_voucher_a)
        assert gl_expense_b not in list(form.fields["gl_account"].queryset)
        assert finance_tax_code_b not in list(form.fields["tax_code"].queryset)
        assert supplier_b not in list(form.fields["party"].queryset)

    def test_finance_charge_form_offers_a_tenantless_caller_nothing(
            self, supplier_a, freight_invoice_a, gl_expense, finance_tax_code_a):
        from apps.scm.forms import LandedCostChargeForm
        form = LandedCostChargeForm(tenant=None, voucher=None)
        for field_name in ("party", "freight_invoice", "gl_account", "tax_code"):
            assert not form.fields[field_name].queryset.exists(), field_name

    @pytest.mark.parametrize("field_name", ["party", "freight_invoice", "gl_account", "tax_code"])
    def test_finance_charge_form_rejects_every_foreign_fk_pk(
            self, tenant_a, finance_voucher_a, supplier_b, freight_invoice_b, gl_expense_b,
            finance_tax_code_b, field_name):
        from apps.scm.forms import LandedCostChargeForm
        foreign = {"party": supplier_b, "freight_invoice": freight_invoice_b,
                   "gl_account": gl_expense_b, "tax_code": finance_tax_code_b}[field_name]
        form = LandedCostChargeForm(data=_finance_charge_post(**{field_name: foreign.pk}),
                                    tenant=tenant_a, voucher=finance_voucher_a)
        assert not form.is_valid()
        assert field_name in form.errors

    @pytest.mark.parametrize("field_name", ["party", "freight_invoice", "gl_account", "tax_code"])
    def test_finance_charge_clean_rejects_a_foreign_fk_even_unnarrowed(
            self, tenant_a, finance_voucher_a, supplier_b, freight_invoice_b, gl_expense_b,
            finance_tax_code_b, field_name):
        """The narrowed dropdowns above are UX; THIS is the check a crafted POST has to get past."""
        from apps.accounting.models import GLAccount, TaxCode
        from apps.core.models import Party
        from apps.scm.forms import LandedCostChargeForm
        from apps.scm.models import FreightInvoice
        foreign = {"party": supplier_b, "freight_invoice": freight_invoice_b,
                   "gl_account": gl_expense_b, "tax_code": finance_tax_code_b}[field_name]
        widened = {"party": Party.objects.all(), "freight_invoice": FreightInvoice.objects.all(),
                   "gl_account": GLAccount.objects.all(),
                   "tax_code": TaxCode.objects.all()}[field_name]
        form = LandedCostChargeForm(data=_finance_charge_post(**{field_name: foreign.pk}),
                                    tenant=tenant_a, voucher=finance_voucher_a)
        form.fields[field_name].queryset = widened
        assert not form.is_valid()
        assert field_name in form.errors
        assert "belongs to another workspace" in _finance_errors_text(form)


# =================================================================================================
# There is deliberately NO form for LandedCostAllocation
# =================================================================================================
class TestFinanceAllocationHasNoForm:
    def test_finance_no_form_exists_for_the_allocation_rows(self):
        """Every column on ``LandedCostAllocation`` is ``editable=False`` and
        ``LandedCostVoucher.allocate()`` is their ONLY writer — the rows are re-written wholesale on
        every re-allocation, so a form over them would be an editable grid whose edits vanish."""
        import apps.scm.forms as scm_forms
        assert not hasattr(scm_forms, "LandedCostAllocationForm")
