"""Inventory 5.18 — form tests: TaxRule + GLPostRule validation at the boundary."""
import pytest
from django.db import IntegrityError

from apps.accounting.models import GLAccount, TaxCode
from apps.inventory.forms import GLPostRuleForm, TaxRuleForm
from apps.inventory.models import GLPostRule, TaxRule
from apps.scm.models import Item, ItemCategory


@pytest.fixture
def finint_tax_code(db, tenant_a):
    return TaxCode.objects.create(tenant=tenant_a, name="Sales Tax", rate_pct=8.25)


@pytest.fixture
def finint_item(db, tenant_a):
    return Item.objects.create(tenant=tenant_a, sku="FIN-F1", name="Form Widget")


@pytest.fixture
def foreign_item(db, tenant_b):
    return Item.objects.create(tenant=tenant_b, sku="FIN-X", name="Foreign Widget")


def test_finint_taxrule_form_creates_numbered_rule(tenant_a, finint_tax_code, db):
    form = TaxRuleForm({"name": "Default", "country": "", "priority": "100",
                        "is_active": "on"}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a  # crud_create assigns tenant before save; mirror that here
    obj.save()
    assert obj.number.startswith("TRT-")


def test_finint_taxrule_form_rejects_foreign_item(tenant_a, foreign_item,
                                                  finint_tax_code, db):
    form = TaxRuleForm({"name": "Bad", "item": foreign_item.pk, "country": "",
                        "priority": "100"}, tenant=tenant_a)
    assert not form.is_valid()
    assert "item" in form.errors


def test_finint_taxrule_form_scopes_item_queryset_to_tenant(tenant_a, foreign_item,
                                                            finint_tax_code, db):
    form = TaxRuleForm(tenant=tenant_a)
    ids = list(form.fields["item"].queryset.values_list("pk", flat=True))
    assert foreign_item.pk not in ids


def test_finint_glpostrule_form_duplicate_event_type_is_form_error(
        tenant_a, gl_accounts_pair, db):
    rule = GLPostRule.objects.create(
        tenant=tenant_a, event_type="cogs", name="First",
        inventory_account=gl_accounts_pair["inventory"],
        offset_account=gl_accounts_pair["cogs"])
    form = GLPostRuleForm({"event_type": "cogs", "name": "Second",
                           "inventory_account": gl_accounts_pair["inventory"].pk,
                           "offset_account": gl_accounts_pair["cogs"].pk}, tenant=tenant_a)
    assert not form.is_valid()  # TenantUniqueMixin turns unique_together into a field error
    assert rule.event_type == "cogs"


def test_finint_glpostrule_form_rejects_identical_accounts(tenant_a, gl_accounts_pair, db):
    inv = gl_accounts_pair["inventory"]
    form = GLPostRuleForm({"event_type": "adjustment", "name": "Same",
                           "inventory_account": inv.pk, "offset_account": inv.pk},
                          tenant=tenant_a)
    assert not form.is_valid()
    assert "offset_account" in form.errors


@pytest.fixture
def gl_accounts_pair(db, tenant_a):
    inv = GLAccount.objects.create(tenant=tenant_a, code="1500", name="Inventory",
                                   account_type="asset")
    cogs = GLAccount.objects.create(tenant=tenant_a, code="5000",
                                    name="Cost of Goods Sold", account_type="expense")
    return {"inventory": inv, "cogs": cogs}
