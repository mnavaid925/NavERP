"""Procurement 6.17 Risk & Compliance Management — the policy attestation form.

**One form, and deliberately only one.**

``PolicyAttestationForm`` files ONE person's obligation to sign ONE published policy by hand —
the single-row companion to ``raise_attestations()``, which raises the whole roster. It carries
exactly ``policy``, ``user`` and ``due_on``. Everything else on the model is excluded and every
exclusion is the same rule: **the ledger's contents are written by the verbs, never typed.**
``status`` moves only through ``acknowledge()`` / ``mark_exempt()``; ``acknowledged_at``,
``acknowledgement_note``, ``exempt_reason``, ``exempted_by``, ``exempted_at`` and ``alert`` are
stamps those verbs make. A form field for "acknowledged at" would let anybody type a signature.

**There is no form for the two verbs, and that is the contract.** The pinned context for
``policyattestation_detail`` is ``policy``, ``can_sign``, ``allowed_actions`` and ``is_admin`` —
no form key — so the sign and exempt POSTs are read straight off ``request.POST`` by the views,
exactly as entity 1's ``screening_clear`` / ``screening_escalate`` read theirs. Both verbs
re-validate on the MODEL (owner-only for a signature, reason-required for an exemption), which is
the guard that a hand-crafted POST also has to get past.

**Why the policy dropdown is narrowed to PUBLISHED, and why it is not also narrowed to
``requires_acknowledgment``.** A draft is not yet the rule and an archived policy is no longer
it, so a sign-off against either records agreement to something nobody is being asked to follow —
refused here, and backstopped in ``PolicyAttestation.clean()``. ``requires_acknowledgment`` is a
different question: it is 6.19's statement of intent for the BULK roster, and
``raise_attestations()`` obeys it strictly (a policy with the flag off raises no rows at all). An
administrator assigning ONE named person is making a deliberate, individual decision, and there
is no reason for the flag to veto it. The two rules are not in tension; they answer different
questions.

**L39, the dead-end check.** Both FK querysets have to be non-empty on an UNBOUND form or the
create page is a form nobody can submit. ``user`` is every active member of the workspace, so it
is non-empty wherever anybody can reach the page. ``policy`` requires at least one published
policy — which is a real precondition, not a dead end, and the page says so and links to 6.19's
library rather than rendering a silent empty ``<select>``.
"""
from django.core.exceptions import NON_FIELD_ERRORS

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# 6.19 OWNS this model (contract §6a). It is already re-exported from
# ``apps.procurement.models``, but the module-direct import is used here for the same reason
# entity 1 uses one: it is the house rule inside these sub-packages, and 6.19's ``*_CHOICES``
# tuples are deliberately NOT hoisted into the package ``__init__``, so one import line reaches
# everything this module needs from that file.
from apps.procurement.models.DocumentKnowledgeManagement.Policies import ProcurementPolicy
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.RiskComplianceManagement.Policies import (
    ATTESTABLE_POLICY_STATUS, PolicyAttestation)


def _attestable_policies(tenant):
    """The policies a sign-off may be filed against: this workspace's PUBLISHED ones."""
    if tenant is None:
        return ProcurementPolicy.objects.none()
    return (ProcurementPolicy.objects.filter(tenant=tenant, status=ATTESTABLE_POLICY_STATUS)
            .order_by("title", "version_number"))


def _workspace_members(tenant):
    """Active users of this workspace, ordered for human scanning."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant, is_active=True).order_by("username")


class PolicyAttestationForm(TenantUniqueMixin, TenantModelForm):
    """Assign one published policy to one person for sign-off.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs, and it earns its place twice over here:

    * ``PolicyAttestation.clean()`` compares each chosen FK's tenant against ``self.tenant_id``,
      so without the stamp every CREATE would be falsely rejected as cross-tenant; and
    * the ``("tenant", "policy", "user")`` constraint is only validated when ``tenant`` is on the
      instance — and assigning the same policy to the same person twice is the single most likely
      mistake on this page. With the stamp it is a form error with a sentence on it; without it,
      an ``IntegrityError`` 500.
    """

    class Meta:
        model = PolicyAttestation
        fields = ["policy", "user", "due_on"]
        # ``due_on`` needs no widget here: TenantModelForm replaces every DateField widget with a
        # type="date" input of its own, so declaring one would be discarded.
        error_messages = {
            NON_FIELD_ERRORS: {
                "unique_together": "That person already has an attestation on file for this "
                                   "policy. Open the existing one rather than filing a second - "
                                   "one obligation per person per policy is what makes the "
                                   "roster countable.",
            },
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows and
            # must not be able to post one either.
            for name in ("policy", "user"):
                self.fields[name].queryset = self.fields[name].queryset.none()
            return

        # TenantModelForm has already scoped both of these to the tenant (each target model
        # carries a ``tenant`` column). The narrowing below is the EXTRA rule per axis — only a
        # published policy can be attested, only an active account can sign — not the tenant
        # boundary itself.
        self.fields["policy"].queryset = _attestable_policies(tenant)
        self.fields["policy"].help_text = (
            "Published policies only. A draft is not yet the rule and an archived one no longer "
            "is, so neither collects sign-offs.")
        self.fields["user"].queryset = _workspace_members(tenant)
        self.fields["user"].help_text = (
            "Whoever is named here is the ONLY person who can sign this off - not you, not an "
            "administrator. If they should not have to, record an exemption instead.")
        self.fields["due_on"].help_text = (
            f"When the sign-off is due. Leave blank for no deadline; the roster raiser uses "
            f"{PolicyAttestation.DEFAULT_ATTESTATION_DUE_DAYS} days from the day it runs.")

        if self.instance.pk:
            # On an EXISTING row the deadline is the only amendable thing, which is what the edit
            # view's docstring and the button's label ("Change the deadline") both say. Re-pointing
            # `policy` or `user` would not be an amendment at all: it would move an obligation off
            # one person and onto another, silently taking the first person off the overdue board
            # - the withdrawal `policyattestation_delete` exists to restrict. `disabled` (rather
            # than a hidden field or a template-side omission) is what makes that hold against a
            # CRAFTED POST too: Django ignores the submitted value for a disabled field entirely
            # and falls back to the instance's own.
            for name in ("policy", "user"):
                self.fields[name].disabled = True
            self.fields["policy"].help_text = (
                "Fixed once assigned - an obligation is against one policy. To put a different "
                "policy to this person, withdraw this row and assign the other one.")
            self.fields["user"].help_text = (
                "Fixed once assigned - an obligation belongs to the person it names. To move it, "
                "withdraw this row and assign the policy to the other person, so the record shows "
                "both facts.")

    def clean_policy(self):
        """Refuse a policy that cannot carry a sign-off, whatever the POST said.

        The narrowed ``<select>`` above is presentation. This runs against the resolved object, so
        a policy that was archived between the page rendering and the form posting is caught here
        rather than filing an obligation against a rule that has been withdrawn.
        """
        policy = self.cleaned_data.get("policy")
        if policy is not None and policy.status != ATTESTABLE_POLICY_STATUS:
            raise ValidationError(
                f"{policy.number} is {policy.get_status_display().lower()}. Sign-offs are only "
                f"collected for a published policy.")
        return policy

    def clean(self):
        cleaned = super().clean()
        # Re-check every tenant-scoped FK against the workspace: the narrowed <select> above is
        # presentation, and a crafted POST never goes near it. ``user`` is included because
        # accounts.User carries its own nullable tenant — a roster must not be able to name
        # somebody from another workspace, or the tenant-less superuser.
        _reject_foreign(self, cleaned, ["policy", "user"])
        return cleaned
