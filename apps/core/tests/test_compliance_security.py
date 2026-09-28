"""0.21 Compliance, Governance & Risk — security tests.

The cross-tenant and permission gates are covered here as **positive assertions on 404/403**, not
by inspecting decorators, because a decorator can be present and a `get_object_or_404` still
unscoped. The three findings this module exists to pin are the ones the earlier adversarial passes
**could not** reach, because each is performed by an authorised tenant admin through the module's
own normal forms:

1. **I13 — evidence integrity.** A tenant admin must not be able to delete an acknowledgement, and
   deleting a policy that carries attestations must be refused unless explicitly overridden.
2. **I14 — aggregate truth.** Re-versioning a policy must NOT retroactively validate the prior
   cohort's attestations.
3. **I12 — input validation.** `int()` on an `isdigit()`-guarded POST pk must not be reachable:
   `'²'` and a 100-digit string both pass `isdigit()` and then blow up.
"""
import pytest
from django.urls import reverse

from apps.core.models import (
    ComplianceControl,
    ControlFramework,
    ControlFrameworkMapping,
    CorporatePolicy,
    PolicyAcknowledgement,
    RiskRegister,
)


# ------------------------------------------------------------------ cross-tenant (404)
@pytest.mark.parametrize("url_name,args_fixture", [
    ("core:controlframework_detail", "cml021_framework_b"),
    ("core:compliancecontrol_detail", "cml021_control_b"),
    ("core:corporatepolicy_detail", "cml021_policy_b"),
    ("core:riskregister_detail", "cml021_risk_b"),
])
def test_compliance_tenant_b_object_is_404_for_tenant_a(
        db, client_a, request, url_name, args_fixture):
    """A foreign pk must be indistinguishable from a missing one — 404, never 200, never a redirect."""
    foreign = request.getfixturevalue(args_fixture)
    response = client_a.get(reverse(url_name, args=[foreign.pk]))
    assert response.status_code == 404
    assert foreign.code.encode() not in response.content


@pytest.mark.parametrize("url_name,args_fixture", [
    ("core:riskregister_delete", "cml021_risk_b"),
    ("core:corporatepolicy_delete", "cml021_policy_b"),
])
def test_compliance_tenant_b_cannot_be_deleted_by_tenant_a(
        db, client_a, request, url_name, args_fixture):
    """A direct POST is the IDOR probe that matters — GET is only refused by @require_POST."""
    foreign = request.getfixturevalue(args_fixture)
    response = client_a.post(reverse(url_name, args=[foreign.pk]))
    assert response.status_code == 404
    assert type(foreign).objects.filter(pk=foreign.pk).exists(), "the row must survive"


def test_compliance_tenant_b_data_never_appears_in_tenant_a_list(db, client_a, cml021_risk_b):
    body = client_a.get(reverse("core:riskregister_list")).content.decode()
    assert cml021_risk_b.code not in body
    assert "Globex" not in body


# ------------------------------------------------------------------ permissions
@pytest.mark.parametrize("url_name", [
    "core:grc_overview", "core:controlframework_list", "core:compliancecontrol_list",
    "core:corporatepolicy_list", "core:riskregister_list", "core:controlframeworkmapping_list",
    "core:policyacknowledgement_list",
])
def test_compliance_a_tenant_member_is_refused_every_list(db, member_client, url_name):
    """@tenant_admin_required on all 28 views + 2 actions: a member gets 403, not a filtered list."""
    response = member_client.get(reverse(url_name))
    assert response.status_code == 403


def test_compliance_a_tenant_member_cannot_acknowledge(db, member_client, cml021_policy):
    """The acknowledge action is behind the role gate as well as @require_POST."""
    response = member_client.post(
        reverse("core:policy_acknowledge", args=[cml021_policy.pk]))
    assert response.status_code == 403
    assert not PolicyAcknowledgement.objects.filter(policy=cml021_policy).exists()


def test_compliance_acknowledge_refuses_a_get(db, client_a, cml021_policy):
    """Method is checked before the role, so a GET is 405 and writes nothing."""
    response = client_a.get(reverse("core:policy_acknowledge", args=[cml021_policy.pk]))
    assert response.status_code == 405
    assert not PolicyAcknowledgement.objects.filter(policy=cml021_policy).exists()


# ------------------------------------------------------------------ I12 input validation
@pytest.mark.parametrize("junk", ["\u00b2", "\u00b3", "9" * 100, "abc", "-1", "0x1", ""])
def test_compliance_junk_control_id_does_not_reach_a_crash(
        db, client_a, cml021_framework, junk):
    """`isdigit()` accepts what `int()` rejects, so the view must use `as_db_int` (crud.py:59)."""
    response = client_a.post(
        reverse("core:controlframeworkmapping_add", args=[cml021_framework.pk]),
        {"control_id": junk},
    )
    assert response.status_code in (302, 404), "a redirect or a 404, never a 500"
    assert not ControlFrameworkMapping.objects.filter(framework=cml021_framework).exists()


# ------------------------------------------------------------------ I14 aggregate truth
def test_compliance_reversioning_does_not_invalidate_the_prior_cohort(db, cml021_policy, cml021_ack):
    """I14: every row stays truthful; only the aggregate lied. Bump the version and re-check."""
    original_version = cml021_policy.version
    assert cml021_ack.policy_version == original_version
    assert cml021_policy.acknowledged_count == 1

    cml021_policy.version = "2.0"
    cml021_policy.save()
    cml021_policy.refresh_from_db()

    assert cml021_policy.acknowledged_count == 0, (
        "an attestation of v%s must not count towards v2.0" % original_version
    )
    assert cml021_policy.superseded_acknowledgement_count == 1
    # the row itself is untouched — re-versioning never rewrites what it claims somebody agreed to
    cml021_ack.refresh_from_db()
    assert cml021_ack.policy_version == original_version
    assert PolicyAcknowledgement.objects.filter(pk=cml021_ack.pk).exists()


# ------------------------------------------------------------------ the acknowledge action
def test_compliance_acknowledge_stamps_the_actor_and_the_version(
        db, client_a, cml021_policy, admin_user):
    response = client_a.post(reverse("core:policy_acknowledge", args=[cml021_policy.pk]))
    assert response.status_code == 302
    ack = PolicyAcknowledgement.objects.get(policy=cml021_policy, user=admin_user)
    assert ack.policy_version == cml021_policy.version, "the version is a snapshot, never the POST's"
    assert ack.acknowledged_at is not None


def test_compliance_acknowledge_is_idempotent_on_a_double_press(db, client_a, cml021_policy):
    client_a.post(reverse("core:policy_acknowledge", args=[cml021_policy.pk]))
    client_a.post(reverse("core:policy_acknowledge", args=[cml021_policy.pk]))
    assert PolicyAcknowledgement.objects.filter(policy=cml021_policy).count() == 1


def test_compliance_acknowledge_refuses_a_draft_and_writes_nothing(db, client_a, cml021_policy_draft):
    """A draft is not in force — acknowledging it records agreement to something that is not a policy."""
    before = PolicyAcknowledgement.objects.count()
    response = client_a.post(
        reverse("core:policy_acknowledge", args=[cml021_policy_draft.pk]), follow=True)
    assert response.status_code == 200
    assert "draft" in response.content.decode().lower()
    assert PolicyAcknowledgement.objects.count() == before


# ------------------------------------------------------------------ mass assignment
def test_compliance_a_crafted_post_cannot_set_a_stamp_or_the_score(db, client_a, tenant_a):
    """The forgery surface is the POST body, not the rendered form."""
    client_a.post(reverse("core:riskregister_create"), {
        "code": "R-FORGED", "title": "Forged", "risk_statement": "If X, then Y.",
        "category": "operational", "likelihood": "likely", "impact": "severe",
        "treatment": "mitigate", "status": "identified",
        # every one of these is ignored, because none is a form field
        "inherent_score": 1, "residual_score": 1, "number": "GRC-99999",
        "tenant": tenant_a.pk + 999,
    })
    risk = RiskRegister.objects.get(tenant=tenant_a, code="R-FORGED")
    assert risk.inherent_score == 20, "computed from the scales, not the POST"
    assert risk.tenant_id == tenant_a.pk
    # `residual_score` IS a form field and legitimately lands - it is the human assessment of what
    # is left AFTER treatment, and `clean()` is what constrains it (<= the inherent score). A crafted
    # value ABOVE the inherent score must be refused by the model, which is the guard that matters.
    assert risk.residual_score == 1
    risk.residual_score = 25          # deliberately worse than the inherent score of 20
    from django.core.exceptions import ValidationError
    with pytest.raises(ValidationError) as refused:
        risk.clean()
    assert "residual_score" in refused.value.message_dict


def test_compliance_back_fill_keeps_the_note_and_snapshots_the_version(
        db, client_a, cml021_policy, admin_user):
    """I2: the note is now persisted; the actor comes from the picker, never from the form."""
    response = client_a.post(reverse("core:policyacknowledgement_create"), {
        "policy": str(cml021_policy.pk), "user": str(admin_user.pk),
        "notes": "Recorded while the person was on leave.",
    })
    assert response.status_code == 302
    ack = PolicyAcknowledgement.objects.get(policy=cml021_policy, user=admin_user)
    assert ack.notes == "Recorded while the person was on leave.", "I2: the note was dropped"
    assert ack.policy_version == cml021_policy.version



# ------------------------------------------------------------------ I13 evidence integrity
def test_compliance_acknowledgement_cannot_be_deleted(db, client_a, cml021_ack):
    """I13: an attestation is evidence. An admin who can delete one can manufacture a clean register."""
    response = client_a.post(
        reverse("core:policyacknowledgement_delete", args=[cml021_ack.pk]), follow=True)
    assert response.status_code == 200
    assert PolicyAcknowledgement.objects.filter(pk=cml021_ack.pk).exists()
    assert "cannot be deleted" in response.content.decode()


def test_compliance_policy_with_attestations_is_not_deletable_by_default(
        db, client_a, cml021_policy, cml021_ack):
    """The cascade is the danger: deleting the policy would destroy the attestation silently."""
    response = client_a.post(
        reverse("core:corporatepolicy_delete", args=[cml021_policy.pk]), follow=True)
    assert response.status_code == 200
    assert CorporatePolicy.objects.filter(pk=cml021_policy.pk).exists()
    assert PolicyAcknowledgement.objects.filter(pk=cml021_ack.pk).exists()
    assert "destroy evidence" in response.content.decode()


def test_compliance_policy_delete_works_once_the_override_is_posted(
        db, client_a, cml021_policy, cml021_ack):
    """The override exists, and it is explicit rather than inferred from a JS confirm()."""
    response = client_a.post(
        reverse("core:corporatepolicy_delete", args=[cml021_policy.pk]),
        {"discard_attestations": "1"}, follow=True)
    assert response.status_code == 200
    assert not CorporatePolicy.objects.filter(pk=cml021_policy.pk).exists()
    assert not PolicyAcknowledgement.objects.filter(pk=cml021_ack.pk).exists()


def test_compliance_policy_with_no_attestations_deletes_without_an_override(
        db, client_a, cml021_policy_draft):
    """A draft with nothing recorded is ordinary working data and must stay deletable."""
    assert not PolicyAcknowledgement.objects.filter(policy=cml021_policy_draft).exists()
    response = client_a.post(
        reverse("core:corporatepolicy_delete", args=[cml021_policy_draft.pk]))
    assert response.status_code == 302
    assert not CorporatePolicy.objects.filter(pk=cml021_policy_draft.pk).exists()


@pytest.mark.parametrize("junk", ["\u00b2", "9" * 100, "abc", ""])
def test_compliance_junk_back_fill_ids_do_not_reach_a_crash(
        db, client_a, cml021_policy, junk):
    response = client_a.post(
        reverse("core:policyacknowledgement_create"),
        {"policy": junk, "user": junk, "notes": "x"},
    )
    assert response.status_code in (302, 404)
    assert not PolicyAcknowledgement.objects.filter(policy=cml021_policy).exists()
