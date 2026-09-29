"""Regression tests for the two defects filed out of scope during 8.6 and fixed afterwards.

Both were found by the review phase and deliberately deferred, then fixed in their own change.
The test names carry the finding id (``filed_d1`` / ``filed_d2``) so a regression points at the
review entry rather than at a feature name.

**D1 — `TenantNumbered.save()` exhaustion.** The retry loop caught ``IntegrityError`` five times
and then FELL THROUGH to ``super().save()`` with ``self.number == ""``, persisting a numbered
document with a blank number. That silently defeats the ``(tenant, number)`` uniqueness the whole
prefix system exists to provide, and the *second* such row then violates it. Reproduced against
MySQL before the fix: one row saved with ``number=''``.

**D2 — `seed_sales` not idempotent across a whole database.** ``_enrichment_request_payload``
includes ``requested_by_id`` and ``_enrichment_request_matches`` compares it, but the seeder
resolved the owner with an UNORDERED ``.first()``. Once a tenant gained a second admin the row
``.first()`` returned could change, so the next run replayed an identical idempotency key with a
different requester and aborted with *"That idempotency key was already used for different
enrichment evidence."* The service was right to refuse; the seeder was wrong to ask.

The interesting part of D2 is the two hypotheses that were WRONG first: the key is not
cross-tenant (the lookup is tenant-scoped) and a same-tenant replay with the same requester is
genuinely idempotent. Only the third hypothesis -- a different ``requested_by`` -- reproduces the
exact error. Asserted below so the reasoning is not lost.
"""
import pytest
from django.db import IntegrityError

from apps.accounts.models import User
from apps.core.models import Party, Tenant
from apps.sales.models import OrderValidationRule
from apps.sales.models import _base as sales_base

pytestmark = pytest.mark.django_db


# ============================================================== D1: number exhaustion


def test_ordermanagement_filed_d1_exhaustion_never_persists_a_blank_number(monkeypatch,
                                                                             db):
    """Five collisions must RAISE, not save the row with `number=''`."""
    tenant = Tenant.objects.create(name="D1 Tenant", slug="d1-tenant")
    calls = {"n": 0}
    taken = "OVR-00001"
    squat = OrderValidationRule(tenant=tenant, name="squat", rule_type="order_value")
    squat.number = taken
    squat.save()

    def always_collide(model, ten, prefix, width=5, field="number"):
        calls["n"] += 1
        return taken

    monkeypatch.setattr(sales_base, "next_number", always_collide)
    rule = OrderValidationRule(tenant=tenant, name="exhausted", rule_type="order_value")
    with pytest.raises(IntegrityError) as exc:
        rule.save()

    assert calls["n"] == 5, "the retry budget should be spent before giving up"
    assert "Could not allocate" in str(exc.value)
    # THE ASSERTION THAT MATTERS: nothing was written.
    assert not OrderValidationRule.objects.filter(tenant=tenant, number="").exists()
    assert not OrderValidationRule.objects.filter(tenant=tenant, name="exhausted").exists()


def test_ordermanagement_filed_d1_a_normal_save_still_mints_and_persists(monkeypatch, db):
    """The fix must not turn the happy path into a raise -- only the exhausted one."""
    tenant = Tenant.objects.create(name="D1 Happy", slug="d1-happy")
    rule = OrderValidationRule(tenant=tenant, name="fine", rule_type="order_value")
    rule.save()
    rule.refresh_from_db()
    assert rule.number.startswith("OVR-")
    assert rule.number != ""
    assert OrderValidationRule.objects.filter(pk=rule.pk).count() == 1


def test_ordermanagement_filed_d1_a_transient_collision_still_recovers(monkeypatch, db):
    """One collision then success must still save -- the retry is not a dead branch."""
    tenant = Tenant.objects.create(name="D1 Transient", slug="d1-transient")
    taken = "OVR-00001"
    squat = OrderValidationRule(tenant=tenant, name="squat", rule_type="order_value")
    squat.number = taken
    squat.save()

    state = {"n": 0}

    def collide_once(model, ten, prefix, width=5, field="number"):
        state["n"] += 1
        return taken if state["n"] == 1 else "OVR-00002"

    monkeypatch.setattr(sales_base, "next_number", collide_once)
    rule = OrderValidationRule(tenant=tenant, name="recovered", rule_type="order_value")
    rule.save()
    rule.refresh_from_db()
    assert rule.number == "OVR-00002"
    assert state["n"] == 2


def test_ordermanagement_filed_d1_an_explicit_number_bypasses_allocation(monkeypatch, db):
    """An explicit `number=` is honoured verbatim and never enters the retry loop."""
    tenant = Tenant.objects.create(name="D1 Explicit", slug="d1-explicit")

    def boom(*a, **k):  # pragma: no cover - must never be called
        raise AssertionError("next_number must not run when number is supplied")

    monkeypatch.setattr(sales_base, "next_number", boom)
    rule = OrderValidationRule(tenant=tenant, name="explicit", rule_type="order_value",
                               number="OVR-99999")
    rule.save()
    rule.refresh_from_db()
    assert rule.number == "OVR-99999"



# ====================================================== D2: seeder owner resolution


def _ordermanagement_d2_event(tenant, user, party, key, changes):
    from apps.sales.services import create_enrichment_event

    return create_enrichment_event(
        tenant, user, party=party, kind="firmographic", source_kind="manual",
        source_name="D2 probe", source_reference="d2:probe", changes=changes,
        idempotency_key=key,
    )


def test_ordermanagement_filed_d2_same_key_same_requester_is_idempotent(db):
    """The baseline: a genuine replay with an identical payload returns the same row."""
    from django.utils import timezone

    stamp = timezone.now().strftime("%H%M%S%f")
    tenant = Tenant.objects.create(name=f"D2 Same {stamp}", slug=f"d2-same-{stamp.lower()}")
    party = Party.objects.create(tenant=tenant, name="D2 Org", kind="organization")
    owner = User.objects.create(username=f"d2s_{stamp.lower()}",
                                email=f"d2s_{stamp.lower()}@x.test",
                                tenant=tenant, is_active=True, is_tenant_admin=True)
    changes = {"industry": {"value": "technology", "confidence": 0.8}}
    first = _ordermanagement_d2_event(tenant, owner, party, "d2-same-key", changes)
    second = _ordermanagement_d2_event(tenant, owner, party, "d2-same-key", changes)
    assert first.pk == second.pk, "a true replay must return the original event"


def test_ordermanagement_filed_d2_same_key_different_requester_is_refused(db):
    """The root cause: `requested_by_id` is part of the comparison, so the OWNER MUST BE STABLE.

    This is what the seeder bug produced -- not a service bug. The refusal is correct behaviour;
    a seeder that varies the requester between runs is the fault.
    """
    from django.utils import timezone

    stamp = timezone.now().strftime("%H%M%S%f")
    tenant = Tenant.objects.create(name=f"D2 Diff {stamp}", slug=f"d2-diff-{stamp.lower()}")
    party = Party.objects.create(tenant=tenant, name="D2 Org", kind="organization")
    admin_a = User.objects.create(username=f"d2a_{stamp.lower()}",
                                  email=f"d2a_{stamp.lower()}@x.test",
                                  tenant=tenant, is_active=True, is_tenant_admin=True)
    admin_b = User.objects.create(username=f"d2b_{stamp.lower()}",
                                  email=f"d2b_{stamp.lower()}@x.test",
                                  tenant=tenant, is_active=True, is_tenant_admin=True)
    changes = {"industry": {"value": "technology", "confidence": 0.8}}
    _ordermanagement_d2_event(tenant, admin_a, party, "d2-diff-key", changes)
    with pytest.raises(Exception) as exc:
        _ordermanagement_d2_event(tenant, admin_b, party, "d2-diff-key", changes)
    assert "idempotency key" in str(exc.value)


def test_ordermanagement_filed_d2_seeder_owner_resolution_is_ordered_and_stable(db):
    """THE FIX. The seeder must resolve the owner with an explicit `order_by("pk")`.

    Without it, a tenant that gains a second admin can resolve to a different row on the next
    run, which is exactly the condition the test above proves aborts a seed.
    """
    import inspect

    from apps.sales.management.commands.seed_sales import Command

    source = inspect.getsource(Command._seed_tenant)
    # Both fallback lookups must be explicitly ordered; an unordered `.first()` is the bug.
    assert source.count('.order_by("pk").first()') == 2, \
        "the seeder owner lookups must both be explicitly ordered by pk"
    # And the bare unordered admin lookup must not survive anywhere in the command.
    cmd_source = inspect.getsource(Command)
    assert "is_tenant_admin=True).first()" not in cmd_source, \
        "an unordered is_tenant_admin .first() is the D2 bug and must not return"
