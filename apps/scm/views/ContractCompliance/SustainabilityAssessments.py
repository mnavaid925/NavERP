"""SCM 4.12 Contract & Compliance Management — ``SustainabilityAssessment`` views.

The ethical-sourcing third of 4.12: a dated ESG scorecard per trading partner, its declaration
checklist and the supplier's own Scope 1/2/3 figures. Five ordinary CRUD views over authored
intent — no verb routes, because nothing here has a workflow the system drives (see the model's
``status`` note). Three things are worth knowing before reading them.

**Not one number on these pages is computed here.** ``overall_score``, ``rating``,
``maturity_level``, ``total_declared_tco2e`` and ``is_expired()`` all come from the model, and
``recompute_rating()`` — called from ``save()`` on every path — is the only writer of the stored
pair. The view never derives a headline of its own, so the list badge, the detail medal and the
carbon report cannot disagree about what a supplier scored.

**The detail page deliberately links to 4.2's ``SupplierRiskAssessment`` for the same party.** Risk
asks "what could this supplier do to *us*" (four factors 1-5, worst factor drives the headline);
sustainability asks "how does this supplier behave" (0-100, themes averaged). Same party, two
different questions, two different arithmetics — putting them side by side is what stops somebody
reading one as the other. The cross-link is READ-ONLY and always tenant-scoped; a party with no risk
assessment renders as "not assessed", never as a green zero.

**Deletes are tenant-admin gated; edits are not.** Revising a scorecard is the daily work of whoever
owns supplier compliance. Destroying the dated record an auditor asks for is not.

Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
template consumes is listed here, not merely the list variable):

* ``scm/compliance/sustainabilityassessment/list.html`` — ``object_list`` + ``page_obj`` + ``q``
  (from ``crud_list``) plus ``status_choices``, ``rating_choices``, ``source_choices`` (each a
  ``[(value, label), …]`` list) and ``parties`` (a ``core.Party`` queryset for the FK filter —
  compare with ``|stringformat:"d"``, never ``|slugify``). The carbon-report chip in this header is
  a plain ``{% url 'scm:carbon_footprint_report' %}`` and needs no context.
* ``scm/compliance/sustainabilityassessment/detail.html`` — ``obj``, ``themes``, ``declarations``,
  ``risk_assessment``, ``risk_level_css``.
    - ``themes`` — the four EcoVadis themes in the model's own order, as
      ``[{"field", "label", "help", "score"}, …]``. ``score`` is 0-100 **or ``None``** for a theme
      nobody scored: render that as "Not scored", never as a 0% bar (unset is not zero — the whole
      reason the columns are nullable). Carbon is deliberately NOT in this list; it is its own card,
      read straight off ``obj.carbon_score``.
    - ``declarations`` — the six-flag checklist as ``[{"field", "label", "help", "declared"}, …]``.
    - ``risk_assessment`` — the party's most recent 4.2 ``SupplierRiskAssessment``, or ``None``.
    - ``risk_level_css`` — the colour-named badge class for that row's ``risk_level``
      (``badge-muted`` when there is none). It is NOT this model's ``rating_css`` — the medal's
      colour comes from ``obj.rating_css`` / ``obj.status_css`` on the model.
* ``scm/compliance/sustainabilityassessment/form.html`` — ``form``, ``is_edit``, and ``obj``
  (``None`` on the create path).
"""
from django.utils.text import capfirst

from apps.scm.views._common import *  # noqa: F401,F403
# _changed builds the redacted {field: new_value} diff that crud_edit records automatically. The
# save path below is hand-rolled (see _sustainabilityassessment_form), so it has to ask for that
# diff rather than inherit it — and importing it beats a second copy of the redaction rules.
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant

# The party rule is defined ONCE, in the form module, and imported here so the create form's select
# and this page's filter dropdown are the same set by construction. `views/_helpers.py` establishes
# the direction (views may depend on forms) for exactly this reason.
from apps.scm.forms.ContractCompliance.SustainabilityAssessments import _assessable_parties
from apps.scm.forms import SustainabilityAssessmentForm
from apps.scm.models import SupplierRiskAssessment, SustainabilityAssessment

#: Badge colour for 4.2's ``SupplierRiskAssessment.risk_level`` on the cross-link card.
#:
#: It lives here rather than on that model because 4.2 predates the "``*_CSS`` dict on the model"
#: convention and 4.12 is additive — it does not edit shipped 4.1-4.11 model files. The mapping is
#: copied VERBATIM from `templates/scm/srm/riskassessment/{list,detail}.html` so the same assessment
#: is the same colour on both modules' pages; `high` and `critical` share red there, and changing
#: that here would make one screen contradict the other.
#: Colour-named only — `badge-success` / `badge-warning` / `badge-danger` DO NOT EXIST in theme.css.
_RISK_LEVEL_CSS = {
    "low": "badge-green",
    "medium": "badge-amber",
    "high": "badge-red",
    "critical": "badge-red",
}

#: The declaration checklist, in the order the detail page renders it.
#:
#: Named EXPLICITLY rather than derived from "every BooleanField on the model". Auto-derivation is
#: drift-proof in the wrong direction here: the day an unrelated flag (an `is_active`, a
#: `needs_review`) is added it would silently render as a compliance declaration a supplier never
#: made — and a compliance checklist is the one list where an extra row is worse than a missing one.
#: The labels are stated because the acronyms do not survive Django's auto-derived verbose_name
#: ("Reach declared", "Rohs declared"); the explanatory text is NOT restated — it is read off each
#: field's own `help_text` below, so there is one copy of it and it lives on the model.
_DECLARATIONS = (
    ("conflict_minerals_declared", "Conflict minerals (3TG / CMRT)"),
    ("reach_declared", "EU REACH / SVHC"),
    ("rohs_declared", "EU RoHS"),
    ("forced_labor_attested", "Forced labour (UFLPA / modern slavery)"),
    ("deforestation_declared", "Deforestation-free (EUDR)"),
    ("code_of_conduct_signed", "Supplier code of conduct"),
)


def _field_help(name):
    """One model field's ``help_text`` — the single copy of what a column actually means.

    A wrong name raises ``FieldDoesNotExist`` at import, which is a loud startup failure rather than
    a page that quietly renders a blank tooltip.
    """
    return SustainabilityAssessment._meta.get_field(name).help_text


def _theme_rows(obj):
    """The four EcoVadis themes as rows for the detail page's bars.

    Iterates ``SustainabilityAssessment.THEMES`` — the same tuple ``recompute_rating()`` averages —
    so the page shows exactly the themes that voted on the medal, and ``carbon_score`` is absent
    here for the same reason it is absent there (EcoVadis scores Carbon on a separate card, and a
    strong carbon page must not be able to lift a supplier's medal over a weak labour theme).

    ``score`` is passed through untouched, ``None`` and all: an unscored theme is a question nobody
    asked, not a zero, and a 0% bar would print a failing grade the assessment never gave.
    """
    rows = []
    for name in SustainabilityAssessment.THEMES:
        field = SustainabilityAssessment._meta.get_field(name)
        rows.append({
            "field": name,
            "label": capfirst(field.verbose_name),
            "help": field.help_text,
            "score": getattr(obj, name),
        })
    return rows


def _declaration_rows(obj):
    """The six declaration flags as a checklist — see :data:`_DECLARATIONS` for why they are named."""
    return [{"field": name, "label": label, "help": _field_help(name),
             "declared": getattr(obj, name)}
            for name, label in _DECLARATIONS]


@login_required
def sustainabilityassessment_list(request):
    """Search + four filters over the tenant's ESG scorecards.

    Every filter goes through ``crud_list``'s own spec, which applies them to the queryset BEFORE it
    paginates — a filter applied afterwards would page over the unfiltered set and quietly show the
    wrong rows on page 2 — and which carries the L11 int-FK guard for ``?party=``, so a hand-typed
    ``?party=abc`` / ``?party=²`` / an over-range value skips the filter instead of raising out of
    ``.filter()``.

    ``rating`` is filterable at all only because it is a stored, indexed column
    (``scm_esg_tnt_rating_idx``). ``maturity_level`` is the same ladder and is deliberately a
    property, so it is shown on the detail page and never offered here — you cannot filter on
    something the database cannot search.

    ``select_related`` covers the two FKs the rows render (``party.name`` and the assessor); without
    it a page of 15 rows is up to 30 extra queries for two columns.
    """
    qs = (SustainabilityAssessment.objects.filter(tenant=request.tenant)
          .select_related("party", "assessed_by"))
    return crud_list(
        request, qs, "scm/compliance/sustainabilityassessment/list.html",
        search_fields=["number", "party__name", "provider"],
        filters=[("status", "status", False), ("rating", "rating", False),
                 ("source", "source", False), ("party", "party_id", True)],
        extra_context={
            # Every dropdown on the filter bar gets its choices from here. A filter with no context
            # to render is the single most common defect in this codebase — the select comes out
            # empty and the filter is unreachable even though the view supports it.
            "status_choices": SustainabilityAssessment.STATUS_CHOICES,
            "rating_choices": SustainabilityAssessment.RATING_CHOICES,
            "source_choices": SustainabilityAssessment.SOURCE_CHOICES,
            "parties": _assessable_parties(request.tenant),
        },
    )


@login_required
def sustainabilityassessment_create(request):
    return _sustainabilityassessment_form(request, instance=None)


@login_required
def sustainabilityassessment_edit(request, pk):
    """Editable at any time, by any member, at any status.

    No status gate on purpose: nothing else in 4.12 moves this row's ``status`` (there are no verb
    routes and no roller here), so it is the assessor's own note about their own work — and locking
    the record on the value the assessor themselves set would mean a typo in a scorecard could only
    be fixed by an administrator. A supplier's rating is also legitimately re-scored in place when
    the provider re-issues it; that is a revision of one dated finding, not a new finding.
    """
    obj = get_object_or_404(SustainabilityAssessment, pk=pk, tenant=request.tenant)
    return _sustainabilityassessment_form(request, instance=obj)


def _sustainabilityassessment_form(request, instance):
    """The shared create/edit save path — hand-rolled, and these are the three reasons.

    1. ``assessed_by`` is stamped from the SESSION on create. It is ``editable=False`` and off the
       form precisely so it cannot be posted, which means something has to write it, and
       ``crud_create`` has no hook for a field it does not know about.
    2. **Both paths land on the detail page.** ``overall_score`` and ``rating`` are derived on save
       and are invisible on the form, so the author cannot see what the system made of their input
       until the record is rendered. ``crud_edit`` can only redirect to a no-argument URL name (the
       list), which would send an editor away from the one page that answers "did the medal move?".
    3. The audit row is written here with ``_changed(form)`` — the same redacted diff ``crud_edit``
       records — because a hand-rolled save path bypasses the helper that would otherwise write it.

    ``crud_list`` and ``crud_delete`` are still used unchanged; only this path needs its own body.
    The tenant check mirrors ``crud_create``'s: a tenant-less user (the superuser, ``tenant=None``)
    must not create an orphan row that no workspace can ever see.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:sustainabilityassessment_list")
    is_edit = instance is not None

    if request.method == "POST":
        form = SustainabilityAssessmentForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            # Only on create: an edit must not re-attribute somebody else's finding to whoever
            # happened to fix a typo in it.
            if not is_edit:
                obj.assessed_by = request.user
            # No recompute call here — SustainabilityAssessment.save() runs recompute_rating()
            # itself on EVERY path, which is what makes the medal impossible to hand-set from a
            # seeder, a shell or a crafted POST. Deriving it again here would be a second writer.
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create", _changed(form))
            # Report the DERIVED headline back, because the form could not show it. "No theme
            # scored" is said in words rather than as 0/100 — unset is not zero.
            headline = (f"overall {obj.overall_score}/100, {obj.get_rating_display().lower()}"
                        if obj.overall_score is not None
                        else "no theme scored yet, so no medal")
            messages.success(request, f"Assessment {obj.number} saved — {headline}.")
            return redirect("scm:sustainabilityassessment_detail", pk=obj.pk)
    else:
        form = SustainabilityAssessmentForm(instance=instance, tenant=request.tenant)

    return render(request, "scm/compliance/sustainabilityassessment/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
def sustainabilityassessment_detail(request, pk):
    """The scorecard, the declarations, the declared carbon — and 4.2's risk view of the same party.

    The risk lookup is ONE query, ordered explicitly rather than leaning on the sibling model's
    ``Meta.ordering``: "the latest" is this page's requirement, and it should not silently change
    the day 4.2 re-orders its own list. It is filtered by ``tenant`` as well as ``party`` even
    though ``party`` already implies the workspace — every view in this app states the tenant filter
    mechanically, so no page depends on an implication holding.
    """
    obj = get_object_or_404(
        SustainabilityAssessment.objects.select_related("party", "assessed_by", "document"),
        pk=pk, tenant=request.tenant)

    risk = (SupplierRiskAssessment.objects
            .filter(tenant=request.tenant, party_id=obj.party_id)
            .order_by("-assessment_date", "-id")
            .first())

    return render(request, "scm/compliance/sustainabilityassessment/detail.html", {
        "obj": obj,
        "themes": _theme_rows(obj),
        "declarations": _declaration_rows(obj),
        # None when this party has never been risk-assessed. The template says "not assessed" —
        # the absence of a risk review is not a low risk score (the 4.11 lesson: never a confident
        # green zero where the truth is "not measured").
        "risk_assessment": risk,
        "risk_level_css": _RISK_LEVEL_CSS.get(getattr(risk, "risk_level", ""), "badge-muted"),
    })


@tenant_admin_required
@require_POST
def sustainabilityassessment_delete(request, pk):
    """Destroy the dated record — tenant-admin only.

    This row IS what an auditor asks for: the finding, who recorded it, the declarations that were
    on file and the evidence document behind them. Editing one is ordinary compliance work and stays
    open to every member; discarding one is not, and the gate sits here rather than on ``_edit`` for
    that reason.

    **Nothing is protected behind it.** No FK anywhere in the app points at
    ``SustainabilityAssessment`` — it is a leaf — so ``crud_delete`` cannot raise ``ProtectedError``
    here and there is deliberately no handler catching one. That is NOT true of its 4.12 sibling
    ``tradelicense_delete``, whose ``TradeDocument.license`` is ``PROTECT`` and which must pre-check.
    Stated so that adding the first FK to this model is a conscious decision to revisit this view,
    not a 500 discovered in production.

    The evidence ``document`` survives: the FK is ``SET_NULL`` from THIS side, so deleting the
    assessment never deletes the file it cited.
    """
    return crud_delete(request, model=SustainabilityAssessment, pk=pk,
                       success_url="scm:sustainabilityassessment_list")
