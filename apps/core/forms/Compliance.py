"""core — 0.21 forms: control frameworks, controls, policies and the risk register.

**The one rule every form in this file obeys: a form may not carry a field its writer does not
own.** `TenantModelForm.__init__` takes `tenant=` and scopes every `ModelChoiceField` whose model
has a `tenant` field, so no form here overrides `__init__` for FK scoping and none may list
`tenant` in `Meta.fields`.

The three exclusions that matter, and why each is a correctness rule rather than tidiness:

* **`number` is never on a form.** It is `editable=False` and minted in the model's `save()`; a
  form carrying it would let a POST choose its own document number.
* **`inherent_score` is never on `RiskRegisterForm`.** It is recomputed from `likelihood` x
  `impact` in `clean()`, so exposing it would let a member post a risk whose score is whatever
  they typed rather than what the two scales say.
* **`user` and `policy_version` are never on `PolicyAcknowledgementForm`.** They are the ACTOR and
  an EVIDENCE STAMP, both written by the POST-only `policy_acknowledge` view. A form carrying
  `user` would let a member acknowledge a policy on somebody else's behalf, which is the forgery
  the 0.16 evidence stamps exist to prevent.

`CorporatePolicy.status` IS on its form, and that is deliberate: it is a lifecycle a person owns,
not workflow state a verb owns. The contrast is 0.20's `ChangeRequest.status`, which is
verb-driven and therefore off its form.
"""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    ComplianceControl,
    ControlFramework,
    ControlFrameworkMapping,
    CorporatePolicy,
    PolicyAcknowledgement,
    RiskRegister,
)


class ControlFrameworkForm(TenantModelForm):
    """Frameworks are created by a person, so this one carries no excluded field but `number`."""

    class Meta:
        model = ControlFramework
        fields = ["code", "name", "framework_type", "version", "authority", "description",
                  "is_active", "adopted_on", "review_due_on", "notes"]


class ComplianceControlForm(TenantModelForm):
    """`owner` IS on this form — assigning a control to a person is an act, not evidence.

    The contrast is deliberate: on 0.18's `VulnerabilityFinding` the assignee is a verb-driven
    stamp, but a control's owner is a plain ownership assignment a workspace admin makes when they
    create the control, exactly as `owner` works on a queue or a ticket.
    """

    class Meta:
        model = ComplianceControl
        fields = ["code", "title", "description", "category", "status", "owner", "frequency",
                  "evidence_reference", "last_reviewed_on", "next_review_on", "notes"]


class ControlFrameworkMappingForm(TenantModelForm):
    """`framework` and `control` are tenant-scoped automatically by `TenantModelForm`.

    The cross-tenant pairing is refused by the MODEL's `clean()` rather than here, because the
    model is the layer that must hold even when the row is built outside a form (a seeder, a data
    fix, a future API).
    """

    class Meta:
        model = ControlFrameworkMapping
        fields = ["framework", "control", "clause_reference", "coverage", "notes"]


class CorporatePolicyForm(TenantModelForm):
    """`status` is user-owned lifecycle, so it belongs here. See the module docstring."""

    class Meta:
        model = CorporatePolicy
        fields = ["code", "title", "summary", "policy_type", "version", "status", "owner",
                  "effective_on", "review_due_on", "requires_acknowledgement", "body", "notes"]


class RiskRegisterForm(TenantModelForm):
    """**`inherent_score` is deliberately absent.** See the module docstring.

    The score is a product of two scales the user picks, so letting them also type the product is
    how a register starts lying about itself. The model recomputes it in `clean()` on every save,
    so even a crafted POST is overwritten rather than stored.
    """

    class Meta:
        model = RiskRegister
        fields = ["code", "title", "risk_statement", "description", "category", "likelihood",
                  "impact", "residual_score", "treatment", "treatment_plan", "status", "owner",
                  "reviewed_on", "next_review_on", "notes"]


class PolicyAcknowledgementForm(TenantModelForm):
    """Only `notes`. Everything else about an acknowledgement is evidence somebody else supplies.

    `tenant` and `policy` come from the view (the URL names the policy), `user` is the signed-in
    actor, `policy_version` is snapshotted from the policy, and `acknowledged_at` is
    `auto_now_add`. Acknowledging a policy without writing a note is a legitimate act, so `notes`
    is optional and the form is honest about having almost nothing to ask.
    """

    class Meta:
        model = PolicyAcknowledgement
        fields = ["notes"]
