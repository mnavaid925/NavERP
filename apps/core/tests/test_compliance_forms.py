"""0.21 Compliance, Governance & Risk — form tests.

The forms are where a forged number or a forged actor would enter, so every test here is about
what a form will NOT accept. A field that is merely "not required" is not the assertion; the
assertion is that the field is not on the form at all, or that the value is recomputed.

1. **A form may not carry a field its writer does not own.** `number` is minted by the model,
   `inherent_score` is derived, and `user`/`policy_version` are evidence stamps. None of the four
   may appear in any `Meta.fields`, because a field that is merely unsettable in the UI is still
   settable by a crafted POST.
2. **The derived score survives a crafted POST** — the form has no such field, so the value
   cannot even reach the model; the model's `clean()` is the second line of defence, tested in
   `test_compliance_models.py`.
3. **FK choices are tenant-scoped** by `TenantModelForm`, so a mapping form cannot offer another
   tenant's framework.
"""
import pytest

from apps.core.forms import (
    ComplianceControlForm,
    ControlFrameworkForm,
    ControlFrameworkMappingForm,
    CorporatePolicyForm,
    PolicyAcknowledgementForm,
    RiskRegisterForm,
)
from apps.core.models import (
    ComplianceControl,
    ControlFramework,
    ControlFrameworkMapping,
    CorporatePolicy,
    PolicyAcknowledgement,
    RiskRegister,
)

#: Fields that must never appear on any 0.21 form, and why. `number` is minted in `save()`;
#: the other three are the module's evidence fields.
_CML021_NEVER_ON_A_FORM = ("number", "inherent_score", "user", "policy_version", "tenant",
                           "acknowledged_at")

_CML021_ALL_FORMS = (
    ControlFrameworkForm, ComplianceControlForm, ControlFrameworkMappingForm,
    CorporatePolicyForm, PolicyAcknowledgementForm, RiskRegisterForm,
)


@pytest.mark.parametrize("form_class", _CML021_ALL_FORMS)
def test_compliance_form_never_exposes_a_field_its_writer_does_not_own(form_class):
    """The forgery surface is `Meta.fields` itself, so assert on the declared list."""
    declared = form_class.Meta.fields
    for forbidden in _CML021_NEVER_ON_A_FORM:
        assert forbidden not in declared, (
            "%s exposes %r; it is minted or derived, never typed" % (
                form_class.__name__, forbidden)
        )


def test_compliance_risk_form_recomputes_the_score_rather_than_trusting_it(db, tenant_a):
    """A crafted `inherent_score` must not survive — it is not a form field, and `clean()` overwrites."""
    form = RiskRegisterForm(
        data={
            "code": "R-FORGED", "title": "Forged", "risk_statement": "If X, then Y.",
            "category": "operational", "likelihood": "likely", "impact": "severe",
            "treatment": "mitigate", "status": "identified",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    risk = form.save(commit=False)
    risk.tenant = tenant_a
    risk.clean()
    # likely (4) x severe (5) = 20, whatever anything else claimed.
    assert risk.inherent_score == 20


def test_compliance_acknowledgement_form_carries_only_notes(db, tenant_a):
    """An attestation is evidence: the form asks for a note and nothing else."""
    form = PolicyAcknowledgementForm(data={}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert set(form.fields) == {"notes"}


def test_compliance_mapping_form_offers_only_this_tenants_frameworks(
        db, tenant_a, tenant_b, cml021_framework, cml021_framework_b):
    """FK scoping is the form's job — a mapping must not be able to name another tenant's row."""
    form = ControlFrameworkMappingForm(tenant=tenant_a)
    offered = {str(pk) for pk in form.fields["framework"].queryset.values_list("pk", flat=True)}
    assert str(cml021_framework.pk) in offered
    assert str(cml021_framework_b.pk) not in offered


def test_compliance_mapping_form_offers_only_this_tenants_controls(
        db, tenant_a, tenant_b, cml021_control, cml021_control_b):
    form = ControlFrameworkMappingForm(tenant=tenant_a)
    offered = {str(pk) for pk in form.fields["control"].queryset.values_list("pk", flat=True)}
    assert str(cml021_control.pk) in offered
    assert str(cml021_control_b.pk) not in offered


def test_compliance_policy_form_refuses_a_published_policy_with_no_effective_date(db, tenant_a):
    """A model guard must reach the form, or the operator only learns at save time."""
    form = CorporatePolicyForm(
        data={"code": "P-1", "title": "T", "summary": "s", "policy_type": "security",
              "version": "1.0", "status": "published"},
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "effective_on" in form.errors


def test_compliance_framework_form_accepts_a_minimal_valid_framework(db, tenant_a):
    form = ControlFrameworkForm(
        data={"code": "F-NEW", "name": "A Framework", "framework_type": "attestation",
              "version": "1.0"},
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.save(commit=False).code == "F-NEW"


def test_compliance_control_form_carries_owner_because_ownership_is_an_act(db, tenant_a, admin_user):
    """The documented contrast with 0.18's verb-driven assignee."""
    assert "owner" in ComplianceControlForm.Meta.fields
    form = ComplianceControlForm(
        data={"code": "C-NEW", "title": "C", "description": "d", "category": "access",
              "status": "not_started", "owner": admin_user.pk},
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.save(commit=False).owner == admin_user


def test_compliance_mapped_choices_are_the_model_choices(db, tenant_a):
    """A dropdown that offers a value the model does not accept is a silent 500 on save."""
    form = ControlFrameworkMappingForm(tenant=tenant_a)
    assert list(form.fields["coverage"].choices) == list(ControlFrameworkMapping.COVERAGE_CHOICES)
