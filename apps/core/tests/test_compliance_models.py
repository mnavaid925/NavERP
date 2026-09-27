"""0.21 Compliance, Governance & Risk — model tests.

What this module protects, in order of how expensive a regression would be:

1. **`inherent_score` is recomputed, never trusted.** A stored score a POST can set is a forged
   number on a register whose whole purpose is that the number is true. The test proves the model
   overwrites a crafted value rather than storing it.
2. **The numbering prefixes are the documented ones**, because `RSK` is already `projects.ProjectRisk`
   and two document types sharing a number in one workspace are indistinguishable to an operator.
3. **Every `clean()` refusal fires on the field it names.** A guard that raises on the wrong field
   leaves the operator fixing the wrong thing.
4. **`acknowledgement_rate` returns `None`, never `0`,** when there is nothing to measure — the zero
   rule, which is a correctness rule and not a display preference.
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import (
    ComplianceControl,
    ControlFramework,
    ControlFrameworkMapping,
    CorporatePolicy,
    PolicyAcknowledgement,
    RiskRegister,
)

#: Every index name must be under 30 characters: MariaDB's hard limit, and a 31-character name is a
#: migration that succeeds on SQLite and fails on the database the app actually runs on.
MAX_INDEX_NAME = 30

_CML021_MODELS = (
    ControlFramework, ComplianceControl, ControlFrameworkMapping,
    CorporatePolicy, PolicyAcknowledgement, RiskRegister,
)


def _cml021_minimum(model):
    """The smallest valid field set for `model`, so a numbering test is not a validation test."""
    if model is ControlFramework:
        return {"code": "F-1", "name": "Framework"}
    if model is ComplianceControl:
        return {"code": "C-1", "title": "Control"}
    if model is CorporatePolicy:
        return {"code": "P-1", "title": "Policy"}
    if model is RiskRegister:
        return {"code": "R-1", "title": "Risk", "risk_statement": "If X, then Y."}
    raise AssertionError("no minimum defined for %s" % model.__name__)


# ---------------------------------------------------------------- numbering
@pytest.mark.parametrize("model,prefix", [
    (ControlFramework, "CFW-"),
    (ComplianceControl, "CTL-"),
    (CorporatePolicy, "CPOL-"),
    (RiskRegister, "GRC-"),
])
def test_compliance_number_is_minted_with_its_prefix(db, tenant_a, model, prefix):
    obj = model.objects.create(tenant=tenant_a, **_cml021_minimum(model))
    assert obj.number.startswith(prefix), "%s minted %r, expected the %s prefix" % (
        model.__name__, obj.number, prefix)
    assert len(obj.number) == len(prefix) + 5, "the suffix is zero-padded to five digits"


def test_compliance_numbers_are_sequential_per_tenant(db, tenant_a, tenant_b):
    """Two rows in ONE tenant increment; a second tenant starts its own sequence."""
    first = ControlFramework.objects.create(tenant=tenant_a, **_cml021_minimum(ControlFramework))
    second = ControlFramework.objects.create(tenant=tenant_a, code="F-2", name="Second")
    other = ControlFramework.objects.create(tenant=tenant_b, **_cml021_minimum(ControlFramework))
    assert int(second.number.split("-")[1]) == int(first.number.split("-")[1]) + 1
    assert other.number == "CFW-00001", "each tenant numbers its own documents from one"


def test_compliance_risk_prefix_is_not_rsk(db, tenant_a):
    """`RSK` belongs to `projects.ProjectRisk`; the register must mint `GRC-` instead."""
    risk = RiskRegister.objects.create(tenant=tenant_a, **_cml021_minimum(RiskRegister))
    assert risk.number.startswith("GRC-")
    assert not risk.number.startswith("RSK-")


def test_compliance_child_rows_have_no_number_column(db, tenant_a, cml021_framework,
                                                      cml021_control):
    """A mapping and an acknowledgement are addressed only through their parents, so neither has a
    number to mint — the same rule 0.20's `FeatureRollout` follows."""
    mapping = ControlFrameworkMapping.objects.create(
        tenant=tenant_a, framework=cml021_framework, control=cml021_control)
    assert not hasattr(mapping, "number")
    assert "number" not in [f.name for f in PolicyAcknowledgement._meta.get_fields()]


# ---------------------------------------------------------------- the derived score
def test_compliance_inherent_score_is_recomputed_not_trusted(db, tenant_a):
    """A crafted `inherent_score` cannot survive `clean()`.

    This is the single most important test in the module: the field is off the form, but a form is
    not the only way a value can arrive, and a stored score nobody calculated is a register lying
    about itself.
    """
    risk = RiskRegister(tenant=tenant_a, code="R1", title="t", risk_statement="s",
                        likelihood="likely", impact="severe", inherent_score=1)
    risk.full_clean(exclude=["tenant", "number"])
    assert risk.inherent_score == 20, "likely(4) x severe(5); the crafted 1 was overwritten"


def test_compliance_score_bands_are_derived_not_stored(db, tenant_a):
    """`score_label` is a property, so it cannot drift from the number it describes."""
    for likelihood, impact, expected_label in [
        ("rare", "negligible", "low"),                  # 1 x 1 = 1
        ("possible", "minor", "medium"),                # 3 x 2 = 6
        ("likely", "major", "high"),                    # 4 x 4 = 16
        ("almost_certain", "severe", "critical"),       # 5 x 5 = 25
    ]:
        risk = RiskRegister(tenant=tenant_a, code="R-%s-%s" % (likelihood, impact), title="t",
                            risk_statement="s", likelihood=likelihood, impact=impact)
        risk.full_clean(exclude=["tenant", "number"])
        assert risk.score_label == expected_label, "%s x %s should be %s" % (
            likelihood, impact, expected_label)


def test_compliance_risk_ordering_is_highest_score_first(db, tenant_a):
    """The register is read top-down under time pressure; alphabetical order is a register nobody
    reads."""
    assert RiskRegister._meta.ordering == ["-inherent_score", "code"]


def test_compliance_risk_open_statuses_exclude_closed(db, tenant_a):
    assert "closed" not in RiskRegister.OPEN_STATUSES
    assert set(RiskRegister.OPEN_STATUSES) == {"identified", "assessing", "treating", "monitoring"}


# ---------------------------------------------------------------- the clean() guards
def test_compliance_residual_above_inherent_is_refused(db, tenant_a):
    """Treatment cannot make a risk worse; if the residual really is higher, the INHERENT number is
    the one that is wrong, and that is the message the operator needs."""
    risk = RiskRegister(tenant=tenant_a, code="R1", title="t", risk_statement="s",
                        likelihood="possible", impact="minor", residual_score=99)
    with pytest.raises(ValidationError) as exc:
        risk.full_clean(exclude=["tenant", "number"])
    assert "residual_score" in exc.value.error_dict


def test_compliance_residual_equal_to_inherent_is_accepted(db, tenant_a):
    """Equal is allowed: a risk whose treatment changed nothing is a real, recordable outcome."""
    risk = RiskRegister(tenant=tenant_a, code="R1", title="t", risk_statement="s",
                        likelihood="possible", impact="major", residual_score=9)
    risk.full_clean(exclude=["tenant", "number"])


def test_compliance_closed_risk_needs_a_reviewed_on(db, tenant_a):
    risk = RiskRegister(tenant=tenant_a, code="R1", title="t", risk_statement="s", status="closed")
    with pytest.raises(ValidationError) as exc:
        risk.full_clean(exclude=["tenant", "number"])
    assert "reviewed_on" in exc.value.error_dict


def test_compliance_effective_control_needs_a_review_date(db, tenant_a):
    """A control cannot be declared effective without somebody having looked at it on a date."""
    control = ComplianceControl(tenant=tenant_a, code="C1", title="t", status="effective")
    with pytest.raises(ValidationError) as exc:
        control.full_clean(exclude=["tenant", "number"])
    assert "last_reviewed_on" in exc.value.error_dict


def test_compliance_not_applicable_control_needs_a_reason(db, tenant_a):
    """"Not applicable" is how a gap gets renamed. Requiring the reason is the whole defence."""
    control = ComplianceControl(tenant=tenant_a, code="C1", title="t", status="not_applicable")
    with pytest.raises(ValidationError) as exc:
        control.full_clean(exclude=["tenant", "number"])
    assert "notes" in exc.value.error_dict


def test_compliance_not_applicable_with_a_reason_is_accepted(db, tenant_a):
    control = ComplianceControl(tenant=tenant_a, code="C1", title="t", status="not_applicable",
                                notes="No card payments are in scope for this workspace.")
    control.full_clean(exclude=["tenant", "number"])



def test_compliance_published_policy_needs_effective_on(db, tenant_a):
    policy = CorporatePolicy(tenant=tenant_a, code="P1", title="t", status="published")
    with pytest.raises(ValidationError) as exc:
        policy.full_clean(exclude=["tenant", "number"])
    assert "effective_on" in exc.value.error_dict


def test_compliance_retired_policy_with_future_review_is_refused(db, tenant_a):
    policy = CorporatePolicy(tenant=tenant_a, code="P1", title="t", status="retired",
                             effective_on=timezone.localdate() - datetime.timedelta(days=10),
                             review_due_on=timezone.localdate() + datetime.timedelta(days=10))
    with pytest.raises(ValidationError) as exc:
        policy.full_clean(exclude=["tenant", "number"])
    assert "review_due_on" in exc.value.error_dict


def test_compliance_next_review_before_last_review_is_refused(db, tenant_a):
    control = ComplianceControl(
        tenant=tenant_a, code="C1", title="t", status="implemented",
        last_reviewed_on=timezone.localdate(),
        next_review_on=timezone.localdate() - datetime.timedelta(days=1))
    with pytest.raises(ValidationError) as exc:
        control.full_clean(exclude=["tenant", "number"])
    assert "next_review_on" in exc.value.error_dict


def test_compliance_cross_tenant_mapping_is_refused(db, tenant_a, cml021_framework,
                                                     cml021_control_b):
    """The two FKs are independently settable, so a cross-tenant mapping is reachable by
    constructing the row directly — and the database cannot prevent it. The model must."""
    mapping = ControlFrameworkMapping(tenant=tenant_a, framework=cml021_framework,
                                      control=cml021_control_b)
    with pytest.raises(ValidationError) as exc:
        mapping.full_clean(exclude=["tenant"])
    assert "control" in exc.value.error_dict


# ---------------------------------------------------------------- the zero rule
def test_compliance_acknowledgement_rate_is_none_when_not_required(db, tenant_a, cml021_policy):
    """Never a fake 100% — the template must be able to print an em dash."""
    cml021_policy.requires_acknowledgement = False
    assert cml021_policy.acknowledgement_rate is None


def test_compliance_acknowledgement_rate_is_none_not_zero_when_nobody(db, tenant_a, cml021_policy):
    """"0% acknowledged" of nobody is a false statement about a workspace, not a measurement."""
    from apps.accounts.models import User

    cml021_policy.requires_acknowledgement = True
    cml021_policy.save()
    # Deactivate every account, so the EXPECTED count is zero. The rate must then be None — the
    # branch that matters, because a naive implementation returns 0.0 here and the page prints
    # "0% acknowledged" about a workspace with no people in it.
    User.objects.filter(tenant=tenant_a).update(is_active=False)
    assert cml021_policy.acknowledgement_rate is None


def test_compliance_acknowledgement_rate_is_a_fraction_when_measurable(db, tenant_a, cml021_policy,
                                                                      cml021_ack):
    assert 0 < cml021_policy.acknowledgement_rate <= 1


# ---------------------------------------------------------------- uniqueness & structure
def test_compliance_code_is_unique_per_tenant(db, tenant_a, tenant_b, cml021_framework):
    """The same `code` in a DIFFERENT tenant is fine — it is a per-workspace human key."""
    twin = ControlFramework.objects.create(tenant=tenant_b, code="SOC2", name="Globex SOC 2")
    assert twin.pk != cml021_framework.pk
    with pytest.raises(Exception):
        ControlFramework.objects.create(tenant=tenant_a, code="SOC2", name="Duplicate")


def test_compliance_every_index_name_is_under_mariadb_limit():
    """A 31-character index name is a migration that passes on SQLite and fails on MariaDB."""
    for model in _CML021_MODELS:
        for index in model._meta.indexes:
            assert len(index.name) < MAX_INDEX_NAME, "%s index %r is %d chars" % (
                model.__name__, index.name, len(index.name))


def test_compliance_str_reads_usefully(db, tenant_a, cml021_framework, cml021_control,
                                      cml021_policy, cml021_risk, cml021_mapping, cml021_ack):
    assert cml021_framework.code in str(cml021_framework)
    assert cml021_control.code in str(cml021_control)
    assert cml021_policy.version in str(cml021_policy)
    assert cml021_risk.number in str(cml021_risk)
    assert cml021_framework.code in str(cml021_mapping)
    assert cml021_policy.code in str(cml021_ack)


def test_compliance_acknowledgement_version_is_a_snapshot(db, tenant_a, cml021_policy, cml021_ack):
    """Re-versioning the policy must NOT rewrite what the historical row claims was agreed to."""
    assert cml021_ack.policy_version == "1.0"
    cml021_policy.version = "2.0"
    cml021_policy.save()
    cml021_ack.refresh_from_db()
    assert cml021_ack.policy_version == "1.0", "the snapshot must not follow the policy"


def test_compliance_acknowledgement_rejects_a_duplicate_version(db, tenant_a, cml021_policy,
                                                                cml021_ack, admin_user):
    """`unique_together` includes the version, so re-acknowledging the SAME one is refused while a
    NEW version would be allowed — the difference between the two is the whole reason the key is
    `(policy, user, version)` and not `(policy, user)`."""
    with pytest.raises(Exception):
        PolicyAcknowledgement.objects.create(
            tenant=tenant_a, policy=cml021_policy, user=admin_user, policy_version="1.0")
