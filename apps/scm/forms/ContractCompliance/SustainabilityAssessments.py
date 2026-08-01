"""SCM 4.12 Contract & Compliance Management — the ``SustainabilityAssessment`` form.

One screen: the four EcoVadis themes, the separate Carbon score, the declaration checklist and the
supplier's declared Scope 1/2/3 figures. Everything that could be *argued about* — the medal, the
overall score, the maturity ladder, the validity window, whether a third-party rating names its
provider — is decided by ``SustainabilityAssessment`` itself (``save()`` → ``recompute_rating()``
and ``clean()``), and **none of it is re-implemented here**. This module's entire job is to hand
that validation a correctly TENANT-SCOPED set of choices.

**Why the derived pair is off the form and not merely read-only.** ``overall_score`` and ``rating``
are ``editable=False`` on the model, so they can never reach a whitelist and a crafted POST that
names them is ignored by the form machinery. A "disabled" widget would be the weaker version of the
same idea — the value would still round-trip through the request. The medal is arithmetic over the
themes, not an opinion, so the only honest input surface is the themes themselves.

**Whitelist, never ``Meta.exclude``.** The blacklist form is the one that silently adopts the next
column somebody adds to the model — which on THIS model would mean the next system stamp landing on
a public form. The list below is the model's editable set minus the five stamps, stated once.
"""
from apps.core.models import Document

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _carrier_parties, _supplier_parties
from apps.scm.models import SustainabilityAssessment


def _assessable_parties(tenant):
    """Parties this tenant can assess for ESG — the counterparties it buys from OR hires to move
    freight.

    Written as the UNION of the two existing helpers rather than a third hand-rolled role filter.
    Today ``_carrier_parties`` (supplier / vendor / partner) is a strict superset of
    ``_supplier_parties`` (supplier / vendor), so the union is presently equal to it — the union is
    spelled out anyway because the day either helper is narrowed, this dropdown must follow the
    *rule* ("buy-from parties plus haul-for-us parties"), not inherit whichever one happened to be
    wider. Both legs already ``.distinct()``, which the OR-combination carries, so a party holding
    two roles still renders one ``<option>``.

    A customer is deliberately not offered: 4.12 assesses the *supply* side, and an ESG scorecard
    for someone we sell to is a different question with a different owner. ``None`` tenant yields an
    empty queryset rather than the unscoped default manager — the same posture every other scoping
    helper in this package takes.

    Lives here rather than in ``views/_helpers.py`` because it is used by exactly ONE entity, and
    the view imports it FROM here so the create form's select and the list page's filter dropdown
    are the same set by construction. (``views/_helpers.py`` establishes the direction: views may
    depend on forms.)
    """
    if tenant is None:
        return Party.objects.none()
    return _supplier_parties(tenant) | _carrier_parties(tenant)


class SustainabilityAssessmentForm(TenantModelForm):
    """A dated ESG scorecard for one trading partner — the themes, the declarations, the carbon."""

    class Meta:
        model = SustainabilityAssessment
        # A WHITELIST. Excluded, and why:
        #   `tenant`          — stamped by the view from the session, never posted (L22).
        #   `number`          — auto-assigned in TenantNumbered.save().
        #   `overall_score`   — DERIVED; recompute_rating() is its only writer.
        #   `rating`          — DERIVED, same writer, which is what stops two assessors disagreeing
        #                       about the medal.
        #   `assessed_by`     — system stamp, written from request.user on create (L22).
        #   `created_at` / `updated_at` — automatic.
        # All five model columns above are already `editable=False`, so listing them here is
        # documentation of the boundary rather than the mechanism enforcing it.
        #
        # `status` IS on the form, unlike TradeDocument/TradeLicense: nothing in 4.12 rolls this
        # status and there are no verb routes on this entity, so it is the assessor's own note about
        # their own work (the SupplierRiskAssessment.status precedent). `is_expired()` still answers
        # from `valid_until`, so the page can legitimately show "Validated" beside "Expired".
        fields = [
            # who / when / where it came from
            "party", "assessment_date", "valid_until", "source", "provider", "status",
            # the scorecard — the four themes that vote, then Carbon, which does not
            "environment_score", "labor_human_rights_score", "ethics_score",
            "sustainable_procurement_score", "carbon_score",
            "strengths", "improvement_areas",
            # the declaration checklist
            "conflict_minerals_declared", "reach_declared", "rohs_declared",
            "forced_labor_attested", "deforestation_declared", "code_of_conduct_signed",
            # supplier-DECLARED carbon (never computed by us)
            "scope1_tco2e", "scope2_tco2e", "scope3_tco2e", "carbon_reporting_year",
            "document", "notes",
        ]
        widgets = {
            "strengths": forms.Textarea(attrs={"rows": 3}),
            "improvement_areas": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Stamp the tenant onto the unsaved instance so SustainabilityAssessment.clean()'s
        # cross-tenant guard on `party` / `document` actually RUNS on create. The create path
        # assigns the tenant only AFTER `is_valid()` (apps/core/crud.py:120-123, and the hand-rolled
        # view mirrors it), so without this the instance is validated with `tenant_id` None — the
        # exact case that guard skips — and the check is dead code on the one path where a crafted
        # POST would exercise it.
        # Not `TenantUniqueMixin`: this model's only unique_together is (tenant, number), and
        # `number` is auto-assigned and off the form, so the mixin's validate_unique half would have
        # nothing to check. Borrowing it for its constructor alone would misname the intent.
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

        # --- the two FK dropdowns, re-filtered from their own managers -----------------------------
        # `TenantModelForm` already narrows any FK whose target carries a `tenant` column, but only
        # `if tenant is not None`; a tenant-less caller falls through to the UNSCOPED default
        # manager. Re-filtering from the model rather than chaining off the base's result makes the
        # scoping true by construction instead of true by the caller behaving.
        #
        # Neither dropdown is narrowed by anything else. `document` is not filtered by
        # `classification` and `party` is not filtered by `is_active`: a supplier suspended today is
        # very often exactly the one somebody is writing an ESG finding about, and an over-narrowed
        # select that renders empty is a screen that can never be completed (L39 §2 — the 4.5
        # `ship_to_address` failure).
        if "party" in self.fields:
            self.fields["party"].queryset = _assessable_parties(self.tenant)
        if "document" in self.fields:
            self.fields["document"].queryset = (
                Document.objects.filter(tenant=self.tenant) if self.tenant is not None
                else Document.objects.none())
