"""8.5 Quote & Proposal Management (CPQ) -- the FORMS lane.

Naming: every test is ``test_quoteproposalcpq_*`` and every module-level helper
``_quoteproposalcpq_*`` so the next sub-module appending nearby cannot shadow
them. Record factories are imported from the models lane rather than from the
package ``conftest.py``, which is owned by another step of the build sequence.

The point of this lane is the **exclusion** rules and the **tenant scoping**,
not the happy path. A CPQ form that lets a user type a derived figure, a system
stamp, or the workflow ``status`` is a data-integrity bug that still returns
HTTP 200, and a form whose FK queryset is not tenant-scoped is an IDOR that
still returns HTTP 302.

Three of the tests here are direct regressions on defects the Phase 4 review
found in this sub-module:
  * C2  -- ``Party`` has no ``is_active`` field, so filtering the account and
           contact querysets on it raised ``FieldError`` and 500'd both pages.
  * I14 -- the optional commercial columns were left ``required=True``, so a
           blank quote line could not be saved at all.
  * M8  -- ``owner`` reassignment is an assignment right, not free text, so a
           non-tenant-admin must not be able to hand a quote to someone else.
"""
from decimal import Decimal

import pytest

from apps.sales.forms.QuoteProposalCPQ.CPQQuoteLines import CPQQuoteLineForm
from apps.sales.forms.QuoteProposalCPQ.CPQQuotes import (
    CPQPortalSignForm,
    CPQQuoteApprovalActionForm,
    CPQQuoteForm,
)
from apps.sales.forms.QuoteProposalCPQ.ProductBundles import ProductBundleOptionForm
from apps.sales.forms.QuoteProposalCPQ.QuoteApprovalRules import QuoteApprovalRuleForm

from apps.sales.tests.test_quote_proposal_cpq_models import (
    _quoteproposalcpq_currency,
    _quoteproposalcpq_doc_template,
    _quoteproposalcpq_item,
    _quoteproposalcpq_line,
    _quoteproposalcpq_opportunity,
    _quoteproposalcpq_party,
    _quoteproposalcpq_price_book,
    _quoteproposalcpq_product,
    _quoteproposalcpq_quote,
    _quoteproposalcpq_tax_code,
    _quoteproposalcpq_user,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Form data builders
# ---------------------------------------------------------------------------

def _quoteproposalcpq_quote_form_data(currency, **overrides):
    data = {
        "name": "Enterprise Rack Package",
        "opportunity": "",
        "account": "",
        "contact": "",
        "price_book": "",
        "currency": str(currency.pk),
        "valid_until": "",
        "is_primary": False,
        "header_discount_pct": "",
        "proposal_template": "",
        "terms_and_conditions": "",
        "notes": "",
        "owner": "",
    }
    data.update({k: ("" if v is None else str(v)) for k, v in overrides.items()})
    return data


def _quoteproposalcpq_line_form_data(**overrides):
    data = {
        "parent_line": "",
        "line_type": "standard",
        "product": "",
        "item": "",
        "uom": "",
        "description": "Rack server",
        "quantity": "2.00",
        "list_price": "",
        "discount_pct": "",
        "unit_price": "250.00",
        "tax_code": "",
        "tax_pct": "",
        "unit_cost": "",
        "is_optional": False,
        "is_selected": True,
        "sequence": "10",
    }
    data.update({k: ("" if v is None else str(v)) for k, v in overrides.items()})
    return data


def _quoteproposalcpq_bundle_form_data(bundle, component, **overrides):
    data = {
        "name": "Blade server option",
        "bundle_product": str(bundle.pk),
        "component_product": str(component.pk),
        "component_item": "",
        "option_group": "Hardware",
        "is_required": False,
        "is_default": False,
        "min_quantity": "1",
        "max_quantity": "10",
        "default_quantity": "1",
        "unit_price_override": "",
        "discount_pct_override": "",
        "compatibility_rule": "none",
        "depends_on_product": "",
        "sort_order": "10",
        "is_active": True,
    }
    data.update({k: ("" if v is None else str(v)) for k, v in overrides.items()})
    return data


def _quoteproposalcpq_rule_form_data(**overrides):
    data = {
        "name": "Executive discount floor",
        "rule_type": "max_discount",
        "discount_threshold_pct": "",
        "min_margin_pct": "",
        "amount_threshold": "",
        "approver_role": "sales_manager",
        "auto_reject": False,
        "priority": "100",
        "is_active": True,
        "description": "",
    }
    data.update({k: ("" if v is None else str(v)) for k, v in overrides.items()})
    return data


# ---------------------------------------------------------------------------
# L22: no system stamp and no derived figure is editable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field_name",
    [
        "tenant",
        "number",
        "quote_group_id",
        "revision_number",
        "revision_of",
        "status",
        "approval_status",
        "approval_rule",
        "approved_by",
        "approved_at",
        "approval_note",
        "subtotal",
        "discount_total",
        "tax_total",
        "total",
        "cost_total",
        "margin_total",
        "margin_pct",
        "proposal_rendered_content",
        "signing_token",
        "signer_name",
        "signer_title",
        "signer_email",
        "signed_at",
        "signature_data",
        "converted_order",
        "crm_quote",
    ],
)
def test_quoteproposalcpq_quote_form_excludes_system_and_workflow_fields(field_name):
    """A user who can type ``status`` or ``total`` can fabricate an approved
    quote, or make the header disagree with its own lines."""
    assert field_name not in CPQQuoteForm.Meta.fields


@pytest.mark.parametrize(
    "field_name",
    ["tenant", "quote", "line_subtotal", "line_tax", "line_total", "line_cost", "line_margin", "margin_pct"],
)
def test_quoteproposalcpq_line_form_excludes_system_and_derived_fields(field_name):
    """The line's parent quote comes from the URL, and its money is derived."""
    assert field_name not in CPQQuoteLineForm.Meta.fields


@pytest.mark.parametrize("field_name", ["tenant", "number"])
def test_quoteproposalcpq_bundle_and_rule_forms_exclude_tenant_and_number(field_name):
    assert field_name not in ProductBundleOptionForm.Meta.fields
    assert field_name not in QuoteApprovalRuleForm.Meta.fields


def test_quoteproposalcpq_quote_form_exposes_exactly_the_contract_fields():
    assert CPQQuoteForm.Meta.fields == [
        "name",
        "opportunity",
        "account",
        "contact",
        "price_book",
        "currency",
        "valid_until",
        "is_primary",
        "header_discount_pct",
        "proposal_template",
        "terms_and_conditions",
        "notes",
        "owner",
    ]


def test_quoteproposalcpq_line_form_exposes_exactly_the_contract_fields():
    assert CPQQuoteLineForm.Meta.fields == [
        "parent_line",
        "line_type",
        "product",
        "item",
        "uom",
        "description",
        "quantity",
        "list_price",
        "discount_pct",
        "unit_price",
        "tax_code",
        "tax_pct",
        "unit_cost",
        "is_optional",
        "is_selected",
        "sequence",
    ]


# ---------------------------------------------------------------------------
# Mass assignment: a posted system stamp is not a form field
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_form_ignores_a_posted_system_stamp(db, tenant_a):
    """A posted tenant / status / total is dropped rather than applied -- the
    mass-assignment guard on the create view."""
    from django.test import Client

    from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote

    admin = _quoteproposalcpq_user(tenant_a, "admin_acme", is_admin=True)
    currency = _quoteproposalcpq_currency()
    client = Client()
    client.force_login(admin)
    data = _quoteproposalcpq_quote_form_data(currency, name="Mass assignment probe")
    data.update(
        {"tenant": "999999", "status": "approved", "total": "1.00", "approval_status": "approved"}
    )
    client.post("/sales/quotes/create/", data)
    quote = CPQQuote.objects.filter(tenant=tenant_a, name="Mass assignment probe").first()
    assert quote is not None
    assert quote.status == "draft"
    assert quote.approval_status == "not_required"
    assert quote.total == Decimal("0.00")


# ---------------------------------------------------------------------------
# C2 regression: instantiating the quote form must not FieldError
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_form_instantiates_against_a_real_party(db, tenant_a):
    """C2: the account and contact querysets filtered ``Party`` on
    ``is_active``, which that model does not have, so FieldError 500'd both the
    create and the edit page. Evaluating the queryset is what raised it."""
    form = CPQQuoteForm(tenant=tenant_a)
    assert form.fields["account"].queryset.model.__name__ == "Party"
    assert list(form.fields["account"].queryset) == []
    assert list(form.fields["contact"].queryset) == []


def test_quoteproposalcpq_quote_form_shows_only_the_tenants_parties(db, tenant_a, tenant_b):
    form = CPQQuoteForm(tenant=tenant_a)
    mine = _quoteproposalcpq_party(tenant_a, name="Acme Ltd")
    theirs = _quoteproposalcpq_party(tenant_b, name="Globex Ltd")
    parties = list(form.fields["account"].queryset)
    assert mine in parties
    assert theirs not in parties



# ---------------------------------------------------------------------------
# I14 regression: the optional commercial columns are optional
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_form_does_not_require_header_discount(db, tenant_a):
    form = CPQQuoteForm(tenant=tenant_a)
    assert form.fields["header_discount_pct"].required is False


def test_quoteproposalcpq_quote_form_saves_with_a_blank_header_discount(db, tenant_a):
    currency = _quoteproposalcpq_currency()
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["header_discount_pct"] == Decimal("0.00")


def test_quoteproposalcpq_line_form_marks_the_optional_columns_not_required(db, tenant_a):
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    form = CPQQuoteLineForm(tenant=tenant_a, quote=quote)
    for field_name in ("list_price", "discount_pct", "tax_pct", "unit_cost"):
        assert form.fields[field_name].required is False, field_name


def test_quoteproposalcpq_line_form_saves_with_blank_pricing_columns(db, tenant_a):
    """I14: list_price / discount_pct / tax_pct / unit_cost were left required, so
    a line could not be entered with only a description and a quantity."""
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    form = CPQQuoteLineForm(_quoteproposalcpq_line_form_data(), tenant=tenant_a, quote=quote)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["list_price"] == Decimal("0.00")
    assert form.cleaned_data["discount_pct"] == Decimal("0.00")
    assert form.cleaned_data["tax_pct"] == Decimal("0.00")
    assert form.cleaned_data["unit_cost"] == Decimal("0.00")


def test_quoteproposalcpq_rule_form_does_not_require_either_threshold(db, tenant_a):
    form = QuoteApprovalRuleForm(tenant=tenant_a)
    assert form.fields["min_margin_pct"].required is False
    assert form.fields["discount_threshold_pct"].required is False


def test_quoteproposalcpq_rule_form_saves_with_blank_thresholds(db, tenant_a):
    """I14: the two thresholds fall back to their model defaults rather than
    demanding input on every rule."""
    form = QuoteApprovalRuleForm(_quoteproposalcpq_rule_form_data(), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["min_margin_pct"] == Decimal("15.00")
    assert form.cleaned_data["discount_threshold_pct"] == Decimal("20.00")



# ---------------------------------------------------------------------------
# M8 regression: owner reassignment is a tenant-admin right
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_form_leaves_owner_open_for_a_tenant_admin(db, tenant_a):
    admin = _quoteproposalcpq_user(tenant_a, "admin_acme", is_admin=True)
    colleague = _quoteproposalcpq_user(tenant_a, "colleague")
    form = CPQQuoteForm(tenant=tenant_a, user=admin)
    assert form.fields["owner"].disabled is False
    assert colleague in form.fields["owner"].queryset


def test_quoteproposalcpq_quote_form_lets_a_tenant_admin_reassign_the_owner(db, tenant_a):
    admin = _quoteproposalcpq_user(tenant_a, "admin_acme", is_admin=True)
    colleague = _quoteproposalcpq_user(tenant_a, "colleague")
    currency = _quoteproposalcpq_currency()
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency, owner=colleague.pk), tenant=tenant_a, user=admin)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["owner"] == colleague


def test_quoteproposalcpq_quote_form_disables_and_narrows_owner_for_a_non_admin(db, tenant_a):
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    other = _quoteproposalcpq_user(tenant_a, "other")
    form = CPQQuoteForm(tenant=tenant_a, user=rep)
    assert form.fields["owner"].disabled is True
    assert list(form.fields["owner"].queryset) == [rep]
    assert other not in form.fields["owner"].queryset


def test_quoteproposalcpq_quote_form_ignores_an_owner_posted_by_a_non_admin(db, tenant_a):
    """M8: a disabled field still reaches cleaned_data, so the form pins it back
    to the acting user rather than trusting the posted value."""
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    other = _quoteproposalcpq_user(tenant_a, "other")
    currency = _quoteproposalcpq_currency()
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency, owner=other.pk), tenant=tenant_a, user=rep)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["owner"] == rep


def test_quoteproposalcpq_quote_form_defaults_owner_to_the_acting_user_on_create(db, tenant_a):
    rep = _quoteproposalcpq_user(tenant_a, "rep_acme", is_admin=False)
    form = CPQQuoteForm(tenant=tenant_a, user=rep)
    assert form.initial.get("owner") == rep.pk



# ---------------------------------------------------------------------------
# Tenant scoping: a foreign pk is refused on every FK the quote form exposes
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_form_accepts_an_own_tenant_party(db, tenant_a):
    currency = _quoteproposalcpq_currency()
    mine = _quoteproposalcpq_party(tenant_a, name="Acme Ltd")
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency, account=mine.pk), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["account"] == mine


def test_quoteproposalcpq_quote_form_rejects_a_foreign_account(db, tenant_a, tenant_b):
    currency = _quoteproposalcpq_currency()
    theirs = _quoteproposalcpq_party(tenant_b, name="Globex Ltd")
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency, account=theirs.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "account" in form.errors


def test_quoteproposalcpq_quote_form_rejects_a_foreign_contact(db, tenant_a, tenant_b):
    currency = _quoteproposalcpq_currency()
    theirs = _quoteproposalcpq_party(tenant_b, name="Globex Contact")
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency, contact=theirs.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "contact" in form.errors


def test_quoteproposalcpq_quote_form_rejects_a_foreign_opportunity(db, tenant_a, tenant_b):
    currency = _quoteproposalcpq_currency()
    theirs = _quoteproposalcpq_opportunity(tenant_b)
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency, opportunity=theirs.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "opportunity" in form.errors


def test_quoteproposalcpq_quote_form_rejects_a_foreign_price_book(db, tenant_a, tenant_b):
    currency = _quoteproposalcpq_currency()
    theirs = _quoteproposalcpq_price_book(tenant_b)
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency, price_book=theirs.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "price_book" in form.errors


def test_quoteproposalcpq_quote_form_rejects_a_foreign_doc_template(db, tenant_a, tenant_b):
    currency = _quoteproposalcpq_currency()
    theirs = _quoteproposalcpq_doc_template(tenant_b)
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency, proposal_template=theirs.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "proposal_template" in form.errors


def test_quoteproposalcpq_quote_form_rejects_a_foreign_owner(db, tenant_a, tenant_b):
    """owner is a user, and a user is tenant-scoped too."""
    admin = _quoteproposalcpq_user(tenant_a, "admin_acme", is_admin=True)
    foreign = _quoteproposalcpq_user(tenant_b, "globex_rep")
    currency = _quoteproposalcpq_currency()
    form = CPQQuoteForm(_quoteproposalcpq_quote_form_data(currency, owner=foreign.pk), tenant=tenant_a, user=admin)
    assert not form.is_valid()
    assert "owner" in form.errors



# ---------------------------------------------------------------------------
# Tenant scoping on the line form, including the parent-line narrowing
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_line_form_accepts_an_own_tenant_product(db, tenant_a):
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    mine = _quoteproposalcpq_product(tenant_a, "My widget")
    form = CPQQuoteLineForm(_quoteproposalcpq_line_form_data(product=mine.pk), tenant=tenant_a, quote=quote)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["product"] == mine


def test_quoteproposalcpq_line_form_rejects_a_foreign_product(db, tenant_a, tenant_b):
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    theirs = _quoteproposalcpq_product(tenant_b, "Foreign widget")
    form = CPQQuoteLineForm(_quoteproposalcpq_line_form_data(product=theirs.pk), tenant=tenant_a, quote=quote)
    assert not form.is_valid()
    assert "product" in form.errors


def test_quoteproposalcpq_line_form_rejects_a_foreign_item(db, tenant_a, tenant_b):
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    theirs = _quoteproposalcpq_item(tenant_b, "Foreign SKU")
    form = CPQQuoteLineForm(_quoteproposalcpq_line_form_data(item=theirs.pk), tenant=tenant_a, quote=quote)
    assert not form.is_valid()
    assert "item" in form.errors


def test_quoteproposalcpq_line_form_rejects_a_foreign_tax_code(db, tenant_a, tenant_b):
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    theirs = _quoteproposalcpq_tax_code(tenant_b, name="Foreign VAT")
    form = CPQQuoteLineForm(_quoteproposalcpq_line_form_data(tax_code=theirs.pk), tenant=tenant_a, quote=quote)
    assert not form.is_valid()
    assert "tax_code" in form.errors


def test_quoteproposalcpq_line_form_rejects_a_parent_line_from_another_quote(db, tenant_a):
    """parent_line is narrowed to the SAME quote -- a component cannot hang off a
    different quote's bundle, which would corrupt both rollups."""
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Mine")
    other = _quoteproposalcpq_quote(tenant_a, currency, name="Theirs")
    foreign_parent = _quoteproposalcpq_line(tenant_a, other, description="Other bundle", line_type="bundle_parent")
    form = CPQQuoteLineForm(
        _quoteproposalcpq_line_form_data(parent_line=foreign_parent.pk), tenant=tenant_a, quote=quote
    )
    assert not form.is_valid()
    assert "parent_line" in form.errors


def test_quoteproposalcpq_line_form_offers_only_this_quotes_root_lines(db, tenant_a):
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency, name="Mine")
    other = _quoteproposalcpq_quote(tenant_a, currency, name="Theirs")
    mine_root = _quoteproposalcpq_line(tenant_a, quote, description="My bundle", line_type="bundle_parent")
    their_root = _quoteproposalcpq_line(tenant_a, other, description="Their bundle", line_type="bundle_parent")
    my_child = _quoteproposalcpq_line(tenant_a, quote, description="My child", parent_line=mine_root, sequence=20)
    form = CPQQuoteLineForm(tenant=tenant_a, quote=quote)
    options = list(form.fields["parent_line"].queryset)
    assert mine_root in options
    assert their_root not in options
    # a component is not itself a valid parent
    assert my_child not in options


def test_quoteproposalcpq_line_form_excludes_itself_from_the_parent_options(db, tenant_a):
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    line = _quoteproposalcpq_line(tenant_a, quote, description="Editable", line_type="bundle_parent")
    form = CPQQuoteLineForm(instance=line, tenant=tenant_a, quote=quote)
    assert line not in form.fields["parent_line"].queryset



# ---------------------------------------------------------------------------
# Bundle and rule forms
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_bundle_form_saves_a_valid_configuration(db, tenant_a):
    bundle = _quoteproposalcpq_product(tenant_a, "Enterprise Rack")
    component = _quoteproposalcpq_product(tenant_a, "Blade Server")
    form = ProductBundleOptionForm(_quoteproposalcpq_bundle_form_data(bundle, component), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["bundle_product"] == bundle
    assert form.cleaned_data["compatibility_rule"] == "none"


def test_quoteproposalcpq_bundle_form_rejects_a_foreign_component_product(db, tenant_a, tenant_b):
    bundle = _quoteproposalcpq_product(tenant_a, "My bundle")
    theirs = _quoteproposalcpq_product(tenant_b, "Foreign component")
    form = ProductBundleOptionForm(_quoteproposalcpq_bundle_form_data(bundle, theirs), tenant=tenant_a)
    assert not form.is_valid()
    assert "component_product" in form.errors


def test_quoteproposalcpq_bundle_form_rejects_a_foreign_bundle_product(db, tenant_a, tenant_b):
    theirs = _quoteproposalcpq_product(tenant_b, "Foreign bundle")
    mine = _quoteproposalcpq_product(tenant_a, "My component")
    form = ProductBundleOptionForm(_quoteproposalcpq_bundle_form_data(theirs, mine), tenant=tenant_a)
    assert not form.is_valid()
    assert "bundle_product" in form.errors


def test_quoteproposalcpq_bundle_form_rejects_a_foreign_component_item(db, tenant_a, tenant_b):
    bundle = _quoteproposalcpq_product(tenant_a, "My bundle")
    component = _quoteproposalcpq_product(tenant_a, "My component")
    theirs = _quoteproposalcpq_item(tenant_b, "Foreign SKU")
    form = ProductBundleOptionForm(
        _quoteproposalcpq_bundle_form_data(bundle, component, component_item=theirs.pk), tenant=tenant_a
    )
    assert not form.is_valid()
    assert "component_item" in form.errors


def test_quoteproposalcpq_bundle_form_runs_the_models_clean_rules(db, tenant_a):
    """ProductBundleOption.clean() refuses a self-referential component and an
    inverted quantity range; ModelForm._post_clean() must surface both."""
    product = _quoteproposalcpq_product(tenant_a, "Self referential")
    form = ProductBundleOptionForm(_quoteproposalcpq_bundle_form_data(product, product), tenant=tenant_a)
    assert not form.is_valid()

    bundle = _quoteproposalcpq_product(tenant_a, "My bundle")
    component = _quoteproposalcpq_product(tenant_a, "My component")
    inverted = ProductBundleOptionForm(
        _quoteproposalcpq_bundle_form_data(bundle, component, min_quantity="5", max_quantity="2"),
        tenant=tenant_a,
    )
    assert not inverted.is_valid()


# ---------------------------------------------------------------------------
# Model validators reached through the forms
# ---------------------------------------------------------------------------

def test_quoteproposalcpq_quote_form_rejects_a_discount_above_one_hundred(db, tenant_a):
    currency = _quoteproposalcpq_currency()
    form = CPQQuoteForm(
        _quoteproposalcpq_quote_form_data(currency, header_discount_pct="150"), tenant=tenant_a
    )
    assert not form.is_valid()
    assert "header_discount_pct" in form.errors


def test_quoteproposalcpq_line_form_rejects_a_negative_quantity(db, tenant_a):
    """quantity has MinValueValidator(0.01) -- a negative line is a
    data-integrity error, not a deep discount."""
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    form = CPQQuoteLineForm(_quoteproposalcpq_line_form_data(quantity="-1"), tenant=tenant_a, quote=quote)
    assert not form.is_valid()
    assert "quantity" in form.errors


def test_quoteproposalcpq_line_form_rejects_a_discount_above_one_hundred(db, tenant_a):
    currency = _quoteproposalcpq_currency()
    quote = _quoteproposalcpq_quote(tenant_a, currency)
    form = CPQQuoteLineForm(_quoteproposalcpq_line_form_data(discount_pct="150"), tenant=tenant_a, quote=quote)
    assert not form.is_valid()
    assert "discount_pct" in form.errors



# ---------------------------------------------------------------------------
# The two plain (non-ModelForm) forms
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action", ["approved", "rejected"])
def test_quoteproposalcpq_approval_action_form_accepts_both_actions(action):
    form = CPQQuoteApprovalActionForm({"action": action, "note": "Reviewed."})
    assert form.is_valid(), form.errors


def test_quoteproposalcpq_approval_action_form_rejects_an_unknown_action():
    form = CPQQuoteApprovalActionForm({"action": "obliterated", "note": ""})
    assert not form.is_valid()
    assert "action" in form.errors


def test_quoteproposalcpq_approval_action_form_demands_a_note_to_reject():
    """A rejection with no reason is unactionable for the rep."""
    form = CPQQuoteApprovalActionForm({"action": "rejected", "note": "   "})
    assert not form.is_valid()
    assert "note" in form.errors


def test_quoteproposalcpq_approval_action_form_allows_an_empty_note_to_approve():
    form = CPQQuoteApprovalActionForm({"action": "approved", "note": ""})
    assert form.is_valid(), form.errors


def test_quoteproposalcpq_portal_sign_form_requires_every_field():
    form = CPQPortalSignForm({})
    assert not form.is_valid()
    for field_name in ("signer_name", "signer_title", "signer_email", "signature_data", "agree_terms"):
        assert field_name in form.errors


def test_quoteproposalcpq_portal_sign_form_rejects_a_malformed_email():
    form = CPQPortalSignForm(
        {
            "signer_name": "Dana Okafor",
            "signer_title": "VP Procurement",
            "signer_email": "not-an-email",
            "signature_data": "Dana Okafor",
            "agree_terms": True,
        }
    )
    assert not form.is_valid()
    assert "signer_email" in form.errors


def test_quoteproposalcpq_portal_sign_form_accepts_a_complete_signature():
    """agree_terms is the customer's binding consent -- it must be explicit."""
    form = CPQPortalSignForm(
        {
            "signer_name": "Dana Okafor",
            "signer_title": "VP Procurement",
            "signer_email": "dana@example.com",
            "signature_data": "Dana Okafor",
            "agree_terms": True,
        }
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["signer_name"] == "Dana Okafor"

