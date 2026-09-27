"""8.5 Quote & Proposal Management (CPQ) -- the MODELS lane.

Naming: every test is ``test_quoteproposalcpq_*`` and every module-level helper
``_quoteproposalcpq_*`` so the next sub-module appending nearby cannot shadow
them (8.1/8.2/8.3/8.4 own the ``leadmanagement``/``opportunitypipeline``/
``contactaccountmanagement``/``salesforecasting`` names in this same package).

This lane pins what the OTHER lanes take for granted: the choice vocabularies,
the number prefixes, the composite indexes migration ``0010`` declares, the
``unique_together`` guards, and the derived money/date properties
(``is_expired``/``is_editable``/``can_convert``) plus the totals that
``cpq_recalc_quote_totals`` writes.

The NULL-vs-ZERO point is load-bearing: ``amount_threshold`` and
``unit_price_override`` are *unknown* when NULL and must never be silently
coerced to ``0``, because ``0`` is a real answer (a zero discount, a zero
override price) and collapsing the two turns "unset" into "always triggers".
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.utils import timezone


# ============================================================ local fixture toolkit
# conftest.py is owned by Phase 6 step 1 and already carries the 8.1-8.4 lanes.
# It has no 8.5 factory, so the CPQ factories live HERE, prefixed.
def _quoteproposalcpq_currency(code="USD", name="US Dollar", symbol="$", **overrides):
    """``accounting.Currency`` is GLOBAL -- it has no tenant FK at all."""
    from apps.accounting.models import Currency

    fields = {"code": code, "name": name, "symbol": symbol, "is_active": True}
    fields.update(overrides)
    return Currency.objects.create(**fields)


def _quoteproposalcpq_party(tenant, name=None, kind="organization", **overrides):
    from apps.core.models import Party

    fields = {
        "tenant": tenant,
        "kind": kind,
        "name": name or f"{tenant.slug.title()} Account",
    }
    fields.update(overrides)
    return Party.objects.create(**fields)


def _quoteproposalcpq_user(tenant, username, is_admin=False, **overrides):
    from apps.accounts.models import User

    fields = {
        "email": f"{username}@{tenant.slug}.example",
        "username": username,
        "password": "TestPass123!",
        "tenant": tenant,
        "is_tenant_admin": is_admin,
    }
    fields.update(overrides)
    return User.objects.create_user(**fields)


def _quoteproposalcpq_product(tenant, name, **overrides):
    from apps.crm.models import Product

    fields = {
        "tenant": tenant,
        "name": name,
        "sku": f"SKU-{tenant.slug.upper()}-{name[:6].upper()}",
        "product_type": "good",
        "unit_price": Decimal("100.00"),
        "cost": Decimal("30.00"),
        "tax_pct": Decimal("0.00"),
        "is_active": True,
    }
    fields.update(overrides)
    return Product.objects.create(**fields)


def _quoteproposalcpq_uom(tenant, code="EA", **overrides):
    from apps.scm.models import UOM

    fields = {"tenant": tenant, "code": code, "name": f"{code} unit", "factor": Decimal("1")}
    fields.update(overrides)
    return UOM.objects.create(**fields)


def _quoteproposalcpq_item(tenant, name, uom=None, **overrides):
    from apps.scm.models import Item

    fields = {
        "tenant": tenant,
        "sku": f"IT-{tenant.slug.upper()}-{name[:6].upper()}",
        "name": name,
        "uom": uom,
        "item_type": "stock",
        "standard_cost": Decimal("30.0000"),
    }
    fields.update(overrides)
    return Item.objects.create(**fields)


def _quoteproposalcpq_tax_code(tenant, name="VAT 10", **overrides):
    from apps.accounting.models import TaxCode

    fields = {
        "tenant": tenant,
        "name": name,
        "tax_type": "vat",
        "rate_pct": Decimal("10.000"),
        "is_active": True,
    }
    fields.update(overrides)
    return TaxCode.objects.create(**fields)


def _quoteproposalcpq_price_book(tenant, name="Standard", **overrides):
    from apps.crm.models import PriceBook

    fields = {"tenant": tenant, "name": name, "currency_code": "USD", "is_active": True}
    fields.update(overrides)
    return PriceBook.objects.create(**fields)


def _quoteproposalcpq_doc_template(tenant, name="Standard Proposal", **overrides):
    from apps.crm.models import DocTemplate

    fields = {
        "tenant": tenant,
        "name": name,
        "template_type": "proposal",
        "body": "<p>{{ quote.name }}</p>",
        "is_active": True,
    }
    fields.update(overrides)
    return DocTemplate.objects.create(**fields)


def _quoteproposalcpq_opportunity(tenant, account=None, currency=None, owner=None, **overrides):
    from apps.crm.models import Opportunity

    fields = {
        "tenant": tenant,
        "name": f"{tenant.slug.title()} CPQ Deal",
        "account": account,
        "stage": "proposal",
        "forecast_category": "pipeline",
        "amount": Decimal("50000.00"),
        "currency": currency,
        "probability": 60,
        "owner": owner,
    }
    fields.update(overrides)
    return Opportunity.objects.create(**fields)


def _quoteproposalcpq_quote(tenant, currency, account=None, owner=None, **overrides):
    from apps.sales.models import CPQQuote

    fields = {
        "tenant": tenant,
        "name": f"{tenant.slug.title()} Enterprise Proposal",
        "currency": currency,
        "account": account,
        "owner": owner,
        "status": "draft",
    }
    fields.update(overrides)
    return CPQQuote.objects.create(**fields)


def _quoteproposalcpq_line(tenant, quote, description="Consulting services", **overrides):
    from apps.sales.models import CPQQuoteLine

    fields = {
        "tenant": tenant,
        "quote": quote,
        "line_type": "standard",
        "description": description,
        "quantity": Decimal("1.00"),
        "list_price": Decimal("100.00"),
        "unit_price": Decimal("100.00"),
        "sequence": 10,
    }
    fields.update(overrides)
    return CPQQuoteLine.objects.create(**fields)


def _quoteproposalcpq_bundle(tenant, bundle_product, component_product, **overrides):
    from apps.sales.models import ProductBundleOption

    fields = {
        "tenant": tenant,
        "name": f"{bundle_product.name} + {component_product.name}",
        "bundle_product": bundle_product,
        "component_product": component_product,
        "option_group": "Components",
    }
    fields.update(overrides)
    return ProductBundleOption.objects.create(**fields)


def _quoteproposalcpq_rule(tenant, name="Executive Discount Floor", **overrides):
    from apps.sales.models import QuoteApprovalRule

    fields = {"tenant": tenant, "name": name, "rule_type": "max_discount"}
    fields.update(overrides)
    return QuoteApprovalRule.objects.create(**fields)


@pytest.fixture
def quoteproposalcpq_tenant_a(tenant_a):
    return tenant_a


@pytest.fixture
def quoteproposalcpq_tenant_b(tenant_b):
    return tenant_b


@pytest.fixture
def quoteproposalcpq_admin_a(db, quoteproposalcpq_tenant_a):
    return _quoteproposalcpq_user(quoteproposalcpq_tenant_a, "admin_acme", is_admin=True)


@pytest.fixture
def quoteproposalcpq_rep_a(db, quoteproposalcpq_tenant_a):
    return _quoteproposalcpq_user(quoteproposalcpq_tenant_a, "rep_acme", is_admin=False)


@pytest.fixture
def quoteproposalcpq_admin_b(db, quoteproposalcpq_tenant_b):
    return _quoteproposalcpq_user(quoteproposalcpq_tenant_b, "admin_globex", is_admin=True)


@pytest.fixture
def quoteproposalcpq_currency(db):
    return _quoteproposalcpq_currency()


@pytest.fixture
def quoteproposalcpq_account_a(db, quoteproposalcpq_tenant_a):
    return _quoteproposalcpq_party(quoteproposalcpq_tenant_a)


@pytest.fixture
def quoteproposalcpq_quote_a(
    db, quoteproposalcpq_tenant_a, quoteproposalcpq_admin_a, quoteproposalcpq_currency,
    quoteproposalcpq_account_a,
):
    return _quoteproposalcpq_quote(
        quoteproposalcpq_tenant_a,
        quoteproposalcpq_currency,
        account=quoteproposalcpq_account_a,
        owner=quoteproposalcpq_admin_a,
    )


# ================================================== choice vocabularies (contract 2)
def test_quoteproposalcpq_quote_status_vocabulary_is_exact():
    from apps.sales.models import CPQQuote

    assert tuple(tuple(c) for c in CPQQuote.STATUS_CHOICES) == (
        ("draft", "Draft"),
        ("in_review", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("presented", "Presented"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("converted", "Converted to Order"),
        ("superseded", "Superseded"),
        ("expired", "Expired"),
    )


def test_quoteproposalcpq_approval_status_vocabulary_is_exact():
    from apps.sales.models import CPQQuote

    assert tuple(tuple(c) for c in CPQQuote.APPROVAL_STATUS_CHOICES) == (
        ("not_required", "Not Required"),
        ("pending", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )


def test_quoteproposalcpq_line_type_vocabulary_is_exact():
    from apps.sales.models import CPQQuoteLine

    assert tuple(tuple(c) for c in CPQQuoteLine.LINE_TYPE_CHOICES) == (
        ("standard", "Standard Item"),
        ("bundle_parent", "Bundle Package Header"),
        ("bundle_component", "Bundle Component"),
        ("optional_addon", "Optional Add-on"),
    )


def test_quoteproposalcpq_bundle_compatibility_vocabulary_is_exact():
    from apps.sales.models import ProductBundleOption

    assert tuple(tuple(c) for c in ProductBundleOption.COMPATIBILITY_CHOICES) == (
        ("none", "None"),
        ("requires", "Requires"),
        ("excludes", "Mutually Exclusive With"),
        ("recommends", "Recommended With"),
    )


def test_quoteproposalcpq_rule_type_vocabulary_is_exact():
    from apps.sales.models import QuoteApprovalRule

    assert tuple(tuple(c) for c in QuoteApprovalRule.RULE_TYPE_CHOICES) == (
        ("max_discount", "Max Discount %"),
        ("min_margin", "Minimum Margin %"),
        ("max_amount", "Max Total Amount"),
        ("composite", "Composite Discount & Margin"),
    )


def test_quoteproposalcpq_approver_role_vocabulary_is_exact():
    from apps.sales.models import QuoteApprovalRule

    assert tuple(tuple(c) for c in QuoteApprovalRule.APPROVER_ROLE_CHOICES) == (
        ("sales_manager", "Sales Manager"),
        ("sales_director", "Sales Director"),
        ("vp_sales", "VP of Sales"),
        ("finance_manager", "Finance Manager"),
        ("cfo", "Chief Financial Officer"),
    )


def test_quoteproposalcpq_the_quote_statuses_match_the_field_choices_on_the_model():
    """The class constant and the FIELD vocabulary must not drift apart."""
    from apps.sales.models import CPQQuote

    field_choices = tuple(tuple(c) for c in CPQQuote._meta.get_field("status").choices)
    assert field_choices == tuple(tuple(c) for c in CPQQuote.STATUS_CHOICES)


# ============================================================ number prefixes
def test_quoteproposalcpq_number_prefixes_are_cpq_bnd_and_qar():
    from apps.sales.models import CPQQuote, ProductBundleOption, QuoteApprovalRule

    assert CPQQuote.NUMBER_PREFIX == "CPQ"
    assert ProductBundleOption.NUMBER_PREFIX == "BND"
    assert QuoteApprovalRule.NUMBER_PREFIX == "QAR"


def test_quoteproposalcpq_a_quote_numbers_itself_with_the_cpq_prefix(quoteproposalcpq_quote_a):
    assert quoteproposalcpq_quote_a.number.startswith("CPQ-")
    assert quoteproposalcpq_quote_a.number == "CPQ-00001"


def test_quoteproposalcpq_numbering_restarts_per_tenant(
    quoteproposalcpq_tenant_a, quoteproposalcpq_tenant_b, quoteproposalcpq_currency,
):
    first_a = _quoteproposalcpq_quote(quoteproposalcpq_tenant_a, quoteproposalcpq_currency)
    second_a = _quoteproposalcpq_quote(quoteproposalcpq_tenant_a, quoteproposalcpq_currency)
    first_b = _quoteproposalcpq_quote(quoteproposalcpq_tenant_b, quoteproposalcpq_currency)

    assert first_a.number == "CPQ-00001"
    assert second_a.number == "CPQ-00002"
    assert first_b.number == "CPQ-00001", "the sequence is per-tenant, not global"


def test_quoteproposalcpq_bundle_and_rule_numbers_use_their_own_prefixes(quoteproposalcpq_tenant_a):
    parent = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Rack")
    child = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Server")
    bundle = _quoteproposalcpq_bundle(quoteproposalcpq_tenant_a, parent, child)
    rule = _quoteproposalcpq_rule(quoteproposalcpq_tenant_a)

    assert bundle.number.startswith("BND-")
    assert rule.number.startswith("QAR-")


def test_quoteproposalcpq_a_quote_seeds_its_own_revision_family(quoteproposalcpq_quote_a):
    """``quote_group_id`` defaults to the quote's own number -- the family's seed."""
    assert quoteproposalcpq_quote_a.quote_group_id == quoteproposalcpq_quote_a.number
    assert quoteproposalcpq_quote_a.revision_number == 1
    assert quoteproposalcpq_quote_a.revision_of_id is None


def test_quoteproposalcpq_every_quote_gets_a_unique_signing_token(quoteproposalcpq_quote_a):
    """The public portal is addressed by this token, so it must exist and be unique."""
    from apps.sales.models import CPQQuote

    assert len(quoteproposalcpq_quote_a.signing_token) == 32
    other = _quoteproposalcpq_quote(quoteproposalcpq_quote_a.tenant, quoteproposalcpq_quote_a.currency)
    assert other.signing_token != quoteproposalcpq_quote_a.signing_token
    assert len(list(CPQQuote.objects.values_list("signing_token", flat=True).distinct())) == 2


# ================================================== unique_together (contract 2)
def test_quoteproposalcpq_quote_declares_tenant_and_number_as_unique(quoteproposalcpq_quote_a):
    assert quoteproposalcpq_quote_a._meta.unique_together == (("tenant", "number"),)


def test_quoteproposalcpq_bundle_and_rule_declare_the_same_unique_together():
    from apps.sales.models import ProductBundleOption, QuoteApprovalRule

    assert ProductBundleOption._meta.unique_together == (("tenant", "number"),)
    assert QuoteApprovalRule._meta.unique_together == (("tenant", "number"),)


def test_quoteproposalcpq_a_duplicate_quote_number_in_one_tenant_is_refused(quoteproposalcpq_quote_a):
    from apps.sales.models import CPQQuote

    duplicate = CPQQuote(
        tenant=quoteproposalcpq_quote_a.tenant,
        name="Cloned name",
        currency=quoteproposalcpq_quote_a.currency,
    )
    duplicate.number = quoteproposalcpq_quote_a.number
    with pytest.raises(IntegrityError):
        duplicate.save()


def test_quoteproposalcpq_the_same_number_is_reusable_by_another_tenant(
    quoteproposalcpq_quote_a, quoteproposalcpq_tenant_b, quoteproposalcpq_currency,
):
    """The guard is ``(tenant, number)`` -- not ``number`` alone."""
    from apps.sales.models import CPQQuote

    twin = CPQQuote(
        tenant=quoteproposalcpq_tenant_b,
        name="Globex twin",
        currency=quoteproposalcpq_currency,
    )
    twin.number = quoteproposalcpq_quote_a.number
    twin.save()
    assert twin.pk != quoteproposalcpq_quote_a.pk


# =============================== composite indexes declared in migration 0010
def test_quoteproposalcpq_migration_0010_adds_exactly_the_six_tenant_composite_indexes():
    """The composite index set is a contract, not an implementation detail.

    Migration 0010 was raised for exactly these six; a dropped index is invisible
    until a register page times out on a large tenant, so pin the migration.
    """
    from pathlib import Path

    import apps.sales.migrations as migrations_pkg

    path = Path(migrations_pkg.__file__).parent / "0010_cpqquote_sales_cpq_tnt_num_idx_and_more.py"
    assert path.exists(), "migration 0010 is missing"
    source = path.read_text(encoding="utf-8")
    for index_name in (
        "sales_cpq_tnt_num_idx",
        "sales_cpq_tnt_appr_idx",
        "sales_bnd_tnt_num_idx",
        "sales_bnd_tnt_act_idx",
        "sales_qar_tnt_num_idx",
        "sales_qar_tnt_act_idx",
    ):
        assert index_name in source, index_name
    assert source.count("migrations.AddIndex(") == 6


def test_quoteproposalcpq_quote_declares_its_six_composite_indexes():
    from apps.sales.models import CPQQuote

    indexes = {(index.name, tuple(index.fields)) for index in CPQQuote._meta.indexes}
    assert indexes == {
        ("sales_cpq_tnt_num_idx", ("tenant", "number")),
        ("sales_cpq_tnt_appr_idx", ("tenant", "approval_status")),
        ("sales_cpq_tnt_status_idx", ("tenant", "status")),
        ("sales_cpq_tnt_group_idx", ("tenant", "quote_group_id")),
        ("sales_cpq_tnt_opp_idx", ("tenant", "opportunity")),
        ("sales_cpq_tnt_prim_idx", ("tenant", "is_primary")),
    }


def test_quoteproposalcpq_bundle_and_rule_declare_their_composite_indexes():
    from apps.sales.models import ProductBundleOption, QuoteApprovalRule

    assert {(i.name, tuple(i.fields)) for i in ProductBundleOption._meta.indexes} == {
        ("sales_bnd_tnt_num_idx", ("tenant", "number")),
        ("sales_bnd_tnt_act_idx", ("tenant", "is_active")),
        ("sales_bnd_bundle_act_idx", ("tenant", "bundle_product", "is_active")),
        ("sales_bnd_comp_prod_idx", ("tenant", "component_product")),
    }
    assert {(i.name, tuple(i.fields)) for i in QuoteApprovalRule._meta.indexes} == {
        ("sales_qar_tnt_num_idx", ("tenant", "number")),
        ("sales_qar_tnt_act_idx", ("tenant", "is_active")),
        ("sales_qar_active_prio_idx", ("tenant", "is_active", "priority")),
    }


def test_quoteproposalcpq_line_declares_its_two_tenant_composite_indexes():
    from apps.sales.models import CPQQuoteLine

    assert {(i.name, tuple(i.fields)) for i in CPQQuoteLine._meta.indexes} == {
        ("sales_cpqln_tnt_quo_idx", ("tenant", "quote")),
        ("sales_cpqln_tnt_parent_idx", ("tenant", "parent_line")),
    }


def test_quoteproposalcpq_makemigrations_reports_no_pending_model_changes(db):
    """A model edit that was never migrated would 500 on a fresh database.

    ``makemigrations`` reads the migration loader history, so it needs the
    ``db`` fixture even though it writes nothing. It is skipped when the suite is
    run with --no-migrations, because that flag installs an empty
    MIGRATION_MODULES map which disables the command outright -- there is no
    migration state to compare the models against in that mode.
    """
    from io import StringIO

    from django.conf import settings
    from django.core.management import call_command

    if getattr(settings, "MIGRATION_MODULES", None):
        pytest.skip("migrations are disabled in this run (--no-migrations)")

    out = StringIO()
    call_command("makemigrations", "sales", "--check", "--dry-run", stdout=out, stderr=out)
    assert "No changes detected" in out.getvalue()


# ================================================================ __str__
def test_quoteproposalcpq_str_renders_number_name_and_revision(quoteproposalcpq_quote_a):
    assert str(quoteproposalcpq_quote_a) == (
        f"{quoteproposalcpq_quote_a.number} · {quoteproposalcpq_quote_a.name} (Rev 1)"
    )


def test_quoteproposalcpq_line_str_names_its_quote_and_sequence(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    line = _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Rack unit", sequence=20
    )
    assert str(line) == f"{quoteproposalcpq_quote_a.number} Line 20: Rack unit"


def test_quoteproposalcpq_bundle_str_shows_the_arrow_and_option_group(quoteproposalcpq_tenant_a):
    parent = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Rack")
    child = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Server")
    bundle = _quoteproposalcpq_bundle(
        quoteproposalcpq_tenant_a, parent, child, option_group="Hardware"
    )
    assert str(bundle) == f"{bundle.number} · {parent.name} → {child.name} (Hardware)"


def test_quoteproposalcpq_rule_str_renders_its_rule_type_display(quoteproposalcpq_tenant_a):
    rule = _quoteproposalcpq_rule(quoteproposalcpq_tenant_a, name="Floor", rule_type="min_margin")
    assert str(rule) == f"{rule.number} · Floor (Minimum Margin %)"


# ======================================================= computed state props
@pytest.mark.parametrize(
    "status,editable",
    [
        ("draft", True),
        ("rejected", True),
        ("in_review", False),
        ("approved", False),
        ("presented", False),
        ("accepted", False),
        ("declined", False),
        ("converted", False),
        ("superseded", False),
        ("expired", False),
    ],
)
def test_quoteproposalcpq_is_editable_is_true_only_for_draft_and_rejected(
    quoteproposalcpq_quote_a, status, editable
):
    quoteproposalcpq_quote_a.status = status
    assert quoteproposalcpq_quote_a.is_editable is editable


@pytest.mark.parametrize(
    "approval_status,approved",
    [
        ("not_required", True),
        ("approved", True),
        ("pending", False),
        ("rejected", False),
    ],
)
def test_quoteproposalcpq_is_approved_treats_not_required_as_approved(
    quoteproposalcpq_quote_a, approval_status, approved
):
    quoteproposalcpq_quote_a.approval_status = approval_status
    assert quoteproposalcpq_quote_a.is_approved is approved


@pytest.mark.parametrize(
    "status,convertible",
    [
        ("approved", True),
        ("presented", True),
        ("accepted", True),
        ("draft", False),
        ("in_review", False),
        ("declined", False),
        ("rejected", False),
    ],
)
def test_quoteproposalcpq_can_convert_is_true_only_for_the_live_statuses(
    quoteproposalcpq_quote_a, status, convertible
):
    quoteproposalcpq_quote_a.status = status
    assert quoteproposalcpq_quote_a.can_convert is convertible


def test_quoteproposalcpq_an_already_converted_quote_cannot_convert_again(quoteproposalcpq_quote_a):
    from apps.scm.models import SalesOrder

    order = SalesOrder.objects.create(
        tenant=quoteproposalcpq_quote_a.tenant,
        customer=quoteproposalcpq_quote_a.account,
        status="draft",
    )
    quoteproposalcpq_quote_a.status = "approved"
    quoteproposalcpq_quote_a.converted_order = order
    assert quoteproposalcpq_quote_a.can_convert is False


def test_quoteproposalcpq_is_expired_is_false_without_a_valid_until_date(quoteproposalcpq_quote_a):
    """A NULL validity is 'open ended', not 'expired' -- NULL is not a past date."""
    assert quoteproposalcpq_quote_a.valid_until is None
    assert quoteproposalcpq_quote_a.is_expired is False


def test_quoteproposalcpq_is_expired_is_true_for_a_past_date_on_a_live_quote(quoteproposalcpq_quote_a):
    quoteproposalcpq_quote_a.valid_until = timezone.localdate() - timezone.timedelta(days=1)
    quoteproposalcpq_quote_a.status = "draft"
    assert quoteproposalcpq_quote_a.is_expired is True


def test_quoteproposalcpq_is_expired_is_false_for_a_future_valid_until(quoteproposalcpq_quote_a):
    quoteproposalcpq_quote_a.valid_until = timezone.localdate() + timezone.timedelta(days=30)
    assert quoteproposalcpq_quote_a.is_expired is False


@pytest.mark.parametrize(
    "status", ["accepted", "declined", "converted", "superseded", "expired"]
)
def test_quoteproposalcpq_is_expired_ignores_a_past_date_on_a_settled_quote(
    quoteproposalcpq_quote_a, status
):
    """Only the four LIVE statuses lapse. A declined quote is not 'expired' too."""
    quoteproposalcpq_quote_a.valid_until = timezone.localdate() - timezone.timedelta(days=90)
    quoteproposalcpq_quote_a.status = status
    assert quoteproposalcpq_quote_a.is_expired is False


# ============================================================== derived money
def test_quoteproposalcpq_a_quote_with_no_lines_totals_to_zero(quoteproposalcpq_quote_a):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    quoteproposalcpq_quote_a.refresh_from_db()
    for field in (
        "subtotal", "discount_total", "tax_total", "total", "cost_total", "margin_total",
    ):
        assert getattr(quoteproposalcpq_quote_a, field) == Decimal("0.00"), field
    assert quoteproposalcpq_quote_a.margin_pct == Decimal("0.00"), "never divide by zero"


def test_quoteproposalcpq_recalc_writes_line_and_header_totals(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    tax_code = _quoteproposalcpq_tax_code(quoteproposalcpq_tenant_a)
    line_one = _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Server",
        quantity=Decimal("2.00"), list_price=Decimal("100.00"), unit_price=Decimal("100.00"),
        tax_code=tax_code, tax_pct=Decimal("10.00"), unit_cost=Decimal("30.00"),
    )
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Support",
        quantity=Decimal("1.00"), list_price=Decimal("50.00"), unit_price=Decimal("50.00"),
        tax_pct=Decimal("0.00"), unit_cost=Decimal("10.00"), sequence=20,
    )

    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    line_one.refresh_from_db()
    quoteproposalcpq_quote_a.refresh_from_db()

    assert line_one.line_subtotal == Decimal("200.00")
    assert line_one.line_tax == Decimal("20.00")
    assert line_one.line_total == Decimal("220.00")
    assert line_one.line_cost == Decimal("60.00")
    assert line_one.line_margin == Decimal("140.00")
    assert line_one.margin_pct == Decimal("70.00")

    assert quoteproposalcpq_quote_a.subtotal == Decimal("250.00")
    assert quoteproposalcpq_quote_a.discount_total == Decimal("0.00")
    assert quoteproposalcpq_quote_a.tax_total == Decimal("20.00")
    assert quoteproposalcpq_quote_a.total == Decimal("270.00")
    assert quoteproposalcpq_quote_a.cost_total == Decimal("70.00")
    assert quoteproposalcpq_quote_a.margin_total == Decimal("180.00")
    assert quoteproposalcpq_quote_a.margin_pct == Decimal("72.00")


def test_quoteproposalcpq_the_header_discount_discounts_subtotal_and_tax(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Server",
        quantity=Decimal("2.00"), list_price=Decimal("100.00"), unit_price=Decimal("100.00"),
        tax_pct=Decimal("10.00"), unit_cost=Decimal("30.00"),
    )
    quoteproposalcpq_quote_a.header_discount_pct = Decimal("10.00")
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    quoteproposalcpq_quote_a.refresh_from_db()

    assert quoteproposalcpq_quote_a.subtotal == Decimal("200.00")
    assert quoteproposalcpq_quote_a.discount_total == Decimal("20.00")
    assert quoteproposalcpq_quote_a.tax_total == Decimal("18.00"), "tax follows the discount"
    assert quoteproposalcpq_quote_a.total == Decimal("198.00")
    # margin is measured against the DISCOUNTED subtotal (180 - 60 = 120), not the
    # gross one -- otherwise a discount would flatter the margin percentage.
    assert quoteproposalcpq_quote_a.cost_total == Decimal("60.00")
    assert quoteproposalcpq_quote_a.margin_total == Decimal("120.00")
    assert quoteproposalcpq_quote_a.margin_pct == Decimal("66.67")


def test_quoteproposalcpq_a_deselected_optional_addon_is_excluded_from_the_header(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Base",
        quantity=Decimal("1.00"), list_price=Decimal("100.00"), unit_price=Decimal("100.00"),
    )
    addon = _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Warranty",
        quantity=Decimal("1.00"), list_price=Decimal("900.00"), unit_price=Decimal("900.00"),
        line_type="optional_addon", is_optional=True, is_selected=False, sequence=20,
    )

    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    addon.refresh_from_db()
    quoteproposalcpq_quote_a.refresh_from_db()

    assert addon.line_subtotal == Decimal("900.00"), "the line itself is still priced"
    assert quoteproposalcpq_quote_a.subtotal == Decimal("100.00")
    assert quoteproposalcpq_quote_a.total == Decimal("100.00")


def test_quoteproposalcpq_a_zero_discount_line_adopts_its_list_price(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    """``unit_price=0`` with a real list price means 'not priced yet', not 'free'."""
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    line = _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Server",
        quantity=Decimal("1.00"), list_price=Decimal("250.00"), unit_price=Decimal("0.00"),
        discount_pct=Decimal("0.00"),
    )
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    line.refresh_from_db()
    assert line.unit_price == Decimal("250.00")
    assert line.line_subtotal == Decimal("250.00")


def test_quoteproposalcpq_a_line_discount_derives_the_effective_unit_price(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    line = _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Server",
        quantity=Decimal("2.00"), list_price=Decimal("100.00"), unit_price=Decimal("100.00"),
        discount_pct=Decimal("20.00"),
    )
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    line.refresh_from_db()
    assert line.unit_price == Decimal("80.00")
    assert line.line_subtotal == Decimal("160.00")


def test_quoteproposalcpq_a_manually_entered_unit_price_survives_recalc(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    """A negotiated price must not be overwritten by the list price."""
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    line = _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Negotiated",
        quantity=Decimal("1.00"), list_price=Decimal("100.00"), unit_price=Decimal("77.50"),
        discount_pct=Decimal("0.00"),
    )
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    line.refresh_from_db()
    assert line.unit_price == Decimal("77.50")


def test_quoteproposalcpq_a_primary_quote_syncs_its_total_to_the_opportunity(
    quoteproposalcpq_tenant_a, quoteproposalcpq_admin_a, quoteproposalcpq_currency,
    quoteproposalcpq_account_a,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    opportunity = _quoteproposalcpq_opportunity(
        quoteproposalcpq_tenant_a, account=quoteproposalcpq_account_a,
        currency=quoteproposalcpq_currency, owner=quoteproposalcpq_admin_a,
    )
    quote = _quoteproposalcpq_quote(
        quoteproposalcpq_tenant_a, quoteproposalcpq_currency,
        account=quoteproposalcpq_account_a, owner=quoteproposalcpq_admin_a,
        opportunity=opportunity, is_primary=True,
    )
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quote, quantity=Decimal("1.00"),
        list_price=Decimal("12500.00"), unit_price=Decimal("12500.00"),
    )

    cpq_recalc_quote_totals(quote, save=True)
    opportunity.refresh_from_db()
    assert opportunity.amount == Decimal("12500.00")
    assert opportunity.currency_id == quoteproposalcpq_currency.pk


def test_quoteproposalcpq_a_non_primary_quote_never_touches_the_opportunity_amount(
    quoteproposalcpq_tenant_a, quoteproposalcpq_admin_a, quoteproposalcpq_currency,
    quoteproposalcpq_account_a,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    opportunity = _quoteproposalcpq_opportunity(
        quoteproposalcpq_tenant_a, account=quoteproposalcpq_account_a,
        currency=quoteproposalcpq_currency, owner=quoteproposalcpq_admin_a,
        amount=Decimal("50000.00"),
    )
    quote = _quoteproposalcpq_quote(
        quoteproposalcpq_tenant_a, quoteproposalcpq_currency,
        account=quoteproposalcpq_account_a, opportunity=opportunity, is_primary=False,
    )
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quote, quantity=Decimal("1.00"),
        list_price=Decimal("999.00"), unit_price=Decimal("999.00"),
    )
    cpq_recalc_quote_totals(quote, save=True)
    opportunity.refresh_from_db()
    assert opportunity.amount == Decimal("50000.00")


# ============================================== derived fields are NOT editable
def test_quoteproposalcpq_every_derived_money_field_is_editable_false():
    """L22: a derived figure a user can type is a data-integrity bug (contract 0.6)."""
    from apps.sales.models import CPQQuote, CPQQuoteLine

    for field_name in (
        "subtotal", "discount_total", "tax_total", "total", "cost_total", "margin_total", "margin_pct",
    ):
        assert CPQQuote._meta.get_field(field_name).editable is False, field_name
    for field_name in (
        "line_subtotal", "line_tax", "line_total", "line_cost", "line_margin", "margin_pct",
    ):
        assert CPQQuoteLine._meta.get_field(field_name).editable is False, field_name


def test_quoteproposalcpq_the_number_and_signing_token_are_not_editable():
    from apps.sales.models import CPQQuote

    assert CPQQuote._meta.get_field("number").editable is False
    assert CPQQuote._meta.get_field("signing_token").editable is False


# ======================================================= NULL is not zero
def test_quoteproposalcpq_a_null_amount_threshold_is_unknown_not_zero(quoteproposalcpq_tenant_a):
    rule = _quoteproposalcpq_rule(quoteproposalcpq_tenant_a, rule_type="max_amount")
    assert rule.amount_threshold is None
    assert rule.amount_threshold != Decimal("0")


def test_quoteproposalcpq_a_null_price_override_is_unknown_not_free(quoteproposalcpq_tenant_a):
    parent = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Rack")
    child = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Server")
    bundle = _quoteproposalcpq_bundle(quoteproposalcpq_tenant_a, parent, child)
    assert bundle.unit_price_override is None
    assert bundle.discount_pct_override is None


def test_quoteproposalcpq_nullable_header_fields_default_to_null_not_zero(quoteproposalcpq_tenant_a):
    """Every optional header field is NULL on a fresh quote, never a silent 0/empty stamp."""
    # Built without an owner, because quoteproposalcpq_quote_a deliberately sets one.
    quote = _quoteproposalcpq_quote(
        quoteproposalcpq_tenant_a, _quoteproposalcpq_currency(), owner=None
    )
    for field_name in (
        "opportunity", "contact", "price_book", "approval_rule", "approved_by",
        "proposal_template", "converted_order", "crm_quote", "owner", "revision_of",
    ):
        assert getattr(quote, f"{field_name}_id") is None, field_name
    for field_name in ("approved_at", "valid_until", "signed_at"):
        assert getattr(quote, field_name) is None, field_name


def test_quoteproposalcpq_a_blank_signer_block_reads_as_blank_not_signed(quoteproposalcpq_quote_a):
    assert quoteproposalcpq_quote_a.signed_at is None
    assert quoteproposalcpq_quote_a.signer_name == ""
    assert quoteproposalcpq_quote_a.signature_data == ""
    assert quoteproposalcpq_quote_a.status == "draft"


# ================================================== ProductBundleOption.clean()
def test_quoteproposalcpq_a_product_cannot_be_a_component_of_itself(quoteproposalcpq_tenant_a):
    product = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Solo")
    bundle = _quoteproposalcpq_bundle(quoteproposalcpq_tenant_a, product, product)
    with pytest.raises(ValidationError):
        bundle.full_clean()


def test_quoteproposalcpq_a_bundle_rejects_min_above_max(quoteproposalcpq_tenant_a):
    parent = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Rack")
    child = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Server")
    bundle = _quoteproposalcpq_bundle(
        quoteproposalcpq_tenant_a, parent, child,
        min_quantity=Decimal("5"), max_quantity=Decimal("2"), default_quantity=Decimal("1"),
    )
    with pytest.raises(ValidationError):
        bundle.full_clean()


def test_quoteproposalcpq_a_bundle_rejects_a_default_quantity_outside_the_bounds(quoteproposalcpq_tenant_a):
    parent = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Rack")
    child = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Server")
    bundle = _quoteproposalcpq_bundle(
        quoteproposalcpq_tenant_a, parent, child,
        min_quantity=Decimal("1"), max_quantity=Decimal("4"), default_quantity=Decimal("9"),
    )
    with pytest.raises(ValidationError):
        bundle.full_clean()


def test_quoteproposalcpq_a_well_formed_bundle_passes_clean(quoteproposalcpq_tenant_a):
    parent = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Rack")
    child = _quoteproposalcpq_product(quoteproposalcpq_tenant_a, "Server")
    bundle = _quoteproposalcpq_bundle(
        quoteproposalcpq_tenant_a, parent, child,
        min_quantity=Decimal("1"), max_quantity=Decimal("4"), default_quantity=Decimal("2"),
    )
    bundle.full_clean()


# =============================================== QuoteApprovalRule.evaluate()
def test_quoteproposalcpq_a_max_discount_rule_fires_past_its_threshold(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    rule = _quoteproposalcpq_rule(
        quoteproposalcpq_tenant_a, rule_type="max_discount",
        discount_threshold_pct=Decimal("20.00"),
    )
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, list_price=Decimal("100.00"),
        unit_price=Decimal("100.00"), discount_pct=Decimal("35.00"),
    )
    triggered, reason = rule.evaluate(quoteproposalcpq_quote_a)
    assert triggered is True
    assert "35" in reason and "20" in reason


def test_quoteproposalcpq_a_max_discount_rule_stays_quiet_below_its_threshold(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    rule = _quoteproposalcpq_rule(
        quoteproposalcpq_tenant_a, rule_type="max_discount",
        discount_threshold_pct=Decimal("20.00"),
    )
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, list_price=Decimal("100.00"),
        unit_price=Decimal("100.00"), discount_pct=Decimal("10.00"),
    )
    assert rule.evaluate(quoteproposalcpq_quote_a) == (False, "")


def test_quoteproposalcpq_a_max_discount_rule_reads_the_header_discount_too(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    """The header discount is a discount: a 0%-line quote still trips a 10% rule."""
    rule = _quoteproposalcpq_rule(
        quoteproposalcpq_tenant_a, rule_type="max_discount",
        discount_threshold_pct=Decimal("10.00"),
    )
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, list_price=Decimal("100.00"),
        unit_price=Decimal("100.00"), discount_pct=Decimal("0.00"),
    )
    quoteproposalcpq_quote_a.header_discount_pct = Decimal("25.00")
    assert rule.evaluate(quoteproposalcpq_quote_a)[0] is True


def test_quoteproposalcpq_a_max_amount_rule_reads_the_null_threshold_as_unset(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    """A NULL ``amount_threshold`` must not compare as 0 and fire on every quote."""
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    rule = _quoteproposalcpq_rule(quoteproposalcpq_tenant_a, rule_type="max_amount")
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, quantity=Decimal("5.00"),
        list_price=Decimal("100.00"), unit_price=Decimal("100.00"),
    )
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    assert rule.amount_threshold is None
    assert rule.evaluate(quoteproposalcpq_quote_a) == (False, "")


def test_quoteproposalcpq_a_max_amount_rule_names_the_currency_in_its_reason(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, quoteproposalcpq_currency,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    rule = _quoteproposalcpq_rule(
        quoteproposalcpq_tenant_a, rule_type="max_amount", amount_threshold=Decimal("100.00")
    )
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, quantity=Decimal("5.00"),
        list_price=Decimal("100.00"), unit_price=Decimal("100.00"),
    )
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    triggered, reason = rule.evaluate(quoteproposalcpq_quote_a)
    assert triggered is True
    assert quoteproposalcpq_currency.code in reason


def test_quoteproposalcpq_a_min_margin_rule_fires_below_the_floor(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    rule = _quoteproposalcpq_rule(
        quoteproposalcpq_tenant_a, rule_type="min_margin", min_margin_pct=Decimal("40.00")
    )
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, quantity=Decimal("1.00"),
        list_price=Decimal("100.00"), unit_price=Decimal("100.00"), unit_cost=Decimal("90.00"),
    )
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    triggered, reason = rule.evaluate(quoteproposalcpq_quote_a)
    assert triggered is True
    assert "10.00" in reason


def test_quoteproposalcpq_a_min_margin_rule_ignores_an_empty_quote(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    """Subtotal 0 means 'nothing priced yet', not a 0% margin breach."""
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    rule = _quoteproposalcpq_rule(
        quoteproposalcpq_tenant_a, rule_type="min_margin", min_margin_pct=Decimal("40.00")
    )
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    assert rule.evaluate(quoteproposalcpq_quote_a) == (False, "")


def test_quoteproposalcpq_a_composite_rule_needs_both_breaches(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    rule = _quoteproposalcpq_rule(
        quoteproposalcpq_tenant_a, rule_type="composite",
        discount_threshold_pct=Decimal("20.00"), min_margin_pct=Decimal("40.00"),
    )
    # Discount breached, margin healthy.
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, quantity=Decimal("1.00"),
        list_price=Decimal("100.00"), unit_price=Decimal("70.00"), unit_cost=Decimal("10.00"),
        discount_pct=Decimal("30.00"),
    )
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    assert rule.evaluate(quoteproposalcpq_quote_a) == (False, ""), "one breach is not composite"


def test_quoteproposalcpq_a_composite_rule_fires_on_both_breaches(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    from apps.sales.cpq_services import cpq_recalc_quote_totals

    rule = _quoteproposalcpq_rule(
        quoteproposalcpq_tenant_a, rule_type="composite",
        discount_threshold_pct=Decimal("20.00"), min_margin_pct=Decimal("40.00"),
    )
    _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, quantity=Decimal("1.00"),
        list_price=Decimal("100.00"), unit_price=Decimal("70.00"), unit_cost=Decimal("60.00"),
        discount_pct=Decimal("30.00"),
    )
    cpq_recalc_quote_totals(quoteproposalcpq_quote_a, save=True)
    triggered, reason = rule.evaluate(quoteproposalcpq_quote_a)
    assert triggered is True
    assert "Composite" in reason


def test_quoteproposalcpq_a_rule_reads_an_explicit_max_line_discount_when_given_one(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    rule = _quoteproposalcpq_rule(
        quoteproposalcpq_tenant_a, rule_type="max_discount",
        discount_threshold_pct=Decimal("20.00"),
    )
    triggered, _ = rule.evaluate(quoteproposalcpq_quote_a, max_line_disc=Decimal("55.00"))
    assert triggered is True


# =============================================== multi-tenancy at the model layer
def test_quoteproposalcpq_a_quote_queryset_is_scoped_to_its_tenant(
    quoteproposalcpq_quote_a, quoteproposalcpq_tenant_b, quoteproposalcpq_currency,
):
    from apps.sales.models import CPQQuote

    _quoteproposalcpq_quote(quoteproposalcpq_tenant_b, quoteproposalcpq_currency)
    assert CPQQuote.objects.filter(tenant=quoteproposalcpq_tenant_b).count() == 1
    assert quoteproposalcpq_quote_a.pk not in list(
        CPQQuote.objects.filter(tenant=quoteproposalcpq_tenant_b).values_list("pk", flat=True)
    )


def test_quoteproposalcpq_deleting_a_quote_cascades_to_its_lines(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    from apps.sales.models import CPQQuoteLine

    _quoteproposalcpq_line(quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a)
    _quoteproposalcpq_line(quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Support")
    assert CPQQuoteLine.objects.filter(quote=quoteproposalcpq_quote_a).count() == 2
    quoteproposalcpq_quote_a.delete()
    assert CPQQuoteLine.objects.filter(quote_id=quoteproposalcpq_quote_a.pk).count() == 0


def test_quoteproposalcpq_a_line_cascades_to_its_bundle_children(
    quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a,
):
    from apps.sales.models import CPQQuoteLine

    parent = _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Package", line_type="bundle_parent"
    )
    child = _quoteproposalcpq_line(
        quoteproposalcpq_tenant_a, quoteproposalcpq_quote_a, description="Component",
        line_type="bundle_component", parent_line=parent, sequence=20,
    )
    parent.delete()
    assert not CPQQuoteLine.objects.filter(pk=child.pk).exists()
