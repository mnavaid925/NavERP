"""Procurement 6.8 Contract Management — consolidated suite (models, gates, security).

One file because the sub-module's contracts are few and sharp: clause drafting,
token signing, locked amendment application, renewal dedupe, and the tenant/admin
gates. Runs under config.settings_test (SQLite in-memory).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.procurement.models import (
    ContractAmendment,
    ContractClause,
    ContractClauseLink,
    ContractMilestone,
    ContractSigner,
    ProcurementAlert,
    expiring_contracts,
    run_renewal_alerts,
)
from apps.scm.models import SupplierContract

pytestmark = pytest.mark.django_db


def _supplier(tenant, name="Probe Supply Co"):
    from apps.core.models import Party, PartyRole
    party = Party.objects.filter(tenant=tenant, name=name).first()
    if party is None:
        party = Party.objects.create(tenant=tenant, kind="organization", name=name)
    PartyRole.objects.get_or_create(
        tenant=tenant, party=party, role="vendor",
        defaults={"status": "active", "start_date": timezone.localdate()})
    return party


@pytest.fixture
def contract(db, tenant_a, admin_user):
    today = timezone.localdate()
    return SupplierContract.objects.create(
        tenant=tenant_a, party=_supplier(tenant_a), title="Probe master agreement",
        contract_type="master", status="active",
        start_date=today - datetime.timedelta(days=340),
        end_date=today + datetime.timedelta(days=15),
        contract_value=Decimal("12000.00"), auto_renew=True,
        renewal_notice_days=30, owner=admin_user)


@pytest.fixture
def clause(db, tenant_a):
    return ContractClause.objects.create(
        tenant=tenant_a, title="Payment terms — net 30", category="payment",
        body="Pay us in thirty days.", is_pre_approved=True)


# -- authoring ---------------------------------------------------------------------------------


def test_clause_link_ordering_and_override(tenant_a, contract, clause):
    second = ContractClause.objects.create(
        tenant=tenant_a, title="Termination", category="termination", body="Bye.")
    a = ContractClauseLink.objects.create(contract=contract, clause=clause, section_order=2)
    b = ContractClauseLink.objects.create(contract=contract, clause=second, section_order=1)
    assert list(contract.procurement_clause_links.order_by("section_order")) == [b, a]
    assert a.effective_text == "Pay us in thirty days."  # standard body when no override
    a.custom_text = "Net fifteen."
    assert a.effective_text == "Net fifteen."           # negotiated wording wins
    with pytest.raises(Exception):
        ContractClauseLink.objects.create(              # unique (contract, clause)
            contract=contract, clause=clause, section_order=3)


def test_clause_link_rejects_cross_tenant_clause(tenant_b, contract):
    foreign = ContractClause.objects.create(
        tenant=tenant_b, title="Foreign clause", category="legal", body="x")
    link = ContractClauseLink(contract=contract, clause=foreign, section_order=1)
    with pytest.raises(Exception):
        link.full_clean()


def test_signer_token_minted_and_completion_derived(tenant_a, contract):
    s1 = ContractSigner.objects.create(
        tenant=tenant_a, contract=contract, role="internal",
        signer_name="A", signer_email="a@x.com")
    s2 = ContractSigner.objects.create(
        tenant=tenant_a, contract=contract, role="supplier",
        signer_name="B", signer_email="b@x.com")
    assert s1.token and len(s1.token) > 40 and s1.token != s2.token
    s1.signed_at = timezone.now()
    assert not all(s.has_responded for s in (s1, s2))
    s2.declined_at = timezone.now()
    assert all(s.has_responded for s in (s1, s2))


# -- amendments --------------------------------------------------------------------------------


def test_amendment_apply_writes_only_set_terms(tenant_a, admin_user, contract):
    amendment = ContractAmendment.objects.create(
        tenant=tenant_a, contract=contract,
        reason="extend", proposed_end_date=timezone.localdate() + datetime.timedelta(days=200),
        requested_by=admin_user)
    locked = SupplierContract.objects.select_for_update().get(pk=contract.pk)
    assert amendment.apply(admin_user, locked) is True
    contract.refresh_from_db()
    assert contract.end_date == amendment.proposed_end_date
    assert contract.auto_renew is True          # untouched term stands
    assert amendment.status == "applied" and amendment.applied_at is not None
    again = ContractAmendment.objects.get(pk=amendment.pk)
    assert again.apply(admin_user, locked) is False   # state machine refuses rewrites


def test_amendment_form_refuses_nothing_to_amend(tenant_a, admin_user, contract):
    from apps.procurement.forms import ContractAmendmentForm
    form = ContractAmendmentForm({"reason": "why not"}, tenant=tenant_a)
    assert not form.is_valid()                  # no proposal + no digest = refused


# -- milestones --------------------------------------------------------------------------------


def test_milestone_amount_required_for_payment_kind(tenant_a, contract):
    from apps.procurement.forms import ContractMilestoneForm
    form = ContractMilestoneForm({"kind": "payment", "title": "P2",
                                  "due_date": timezone.localdate()}, tenant=tenant_a)
    assert not form.is_valid() and "amount" in form.errors


def test_milestone_complete_stamps_actor(client_a, admin_user, tenant_a, contract):
    mile = ContractMilestone.objects.create(
        tenant=tenant_a, contract=contract, kind="deliverable",
        title="Kickoff deck", due_date=timezone.localdate())
    r = client_a.post(reverse("procurement:milestone_complete", args=[mile.pk]),
                      {"action": "complete"})
    mile.refresh_from_db()
    assert r.status_code == 302 and mile.status == "completed"
    assert mile.completed_by_id == admin_user.id


# -- renewals engine ---------------------------------------------------------------------------


def test_expiry_window_and_alert_dedupe(tenant_a, admin_user, contract):
    rows = expiring_contracts(tenant_a)
    assert any(row["contract"].pk == contract.pk for row in rows)
    first = run_renewal_alerts(tenant_a, admin_user)
    assert first["raised"] >= 1
    second = run_renewal_alerts(tenant_a, admin_user)
    assert second["raised"] == 0
    alert = ProcurementAlert.objects.filter(
        tenant=tenant_a, kind="contract",
        link_url=f"/scm/contracts/{contract.pk}/").first()
    assert alert is not None


# -- views: public token flow + tenancy/gates --------------------------------------------------


def test_public_sign_flow_end_to_end(tenant_a, contract):
    signer = ContractSigner.objects.create(
        tenant=tenant_a, contract=contract, role="supplier",
        signer_name="S", signer_email="s@x.com")
    anon = Client()
    r = anon.get(reverse("procurement:contract_sign_page", args=[signer.token]))
    assert r.status_code == 200
    signer.refresh_from_db()
    assert signer.viewed_at is not None
    r = anon.post(reverse("procurement:contract_sign_page", args=[signer.token]),
                  {"action": "decline"})
    signer.refresh_from_db()
    assert r.status_code == 302 and signer.declined_at is not None
    r = anon.post(reverse("procurement:contract_sign_page", args=[signer.token]),
                  {"action": "sign"})            # evidence kept, second response inert
    signer.refresh_from_db()
    assert signer.signed_at is None


def test_unknown_token_404_and_idor_404(client_a, client_b, tenant_a, tenant_b, contract):
    assert client_a.get(reverse("procurement:contract_sign_page",
                                args=["z" * 43])).status_code == 404
    other = SupplierContract.objects.create(
        tenant=tenant_b, party=_supplier(tenant_b, "Other Supply"),
        title="Globex deal", status="active")
    assert client_a.get(reverse("procurement:contract_detail",
                                args=[other.pk])).status_code == 404


def test_admin_gates_on_legal_writes(member_client, admin_user, tenant_a):
    r = member_client.get(reverse("procurement:clause_create"))
    assert r.status_code in (302, 403)


def test_register_isolates_tenants(client_b, tenant_a, contract):
    r = client_b.get(reverse("procurement:contract_list"))
    assert r.status_code == 200
    assert f"/procurement/contracts/{contract.pk}/".encode() not in r.content
