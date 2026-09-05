"""Procurement 6.19 Document & Knowledge Management — ProcurementPolicy views.

The **Procurement Policy Library** bullet: the register (search, three facets, a review facet,
pagination), detail, create, edit, delete — plus two POST-only verbs, publish and archive.

The rules this module enforces, because they are what the library is for:

1. **A policy documents; it never enforces.** Nothing in this module reads ``threshold_amount``,
   ``threshold_basis`` or ``threshold_currency`` to decide anything. There is no branch on those
   columns anywhere below — they are rendered and nothing else. Approval bands are 6.3's
   ``ApprovalRoutingRule`` rows, which is the only place a number in this codebase decides who
   has to sign. :data:`ADVISORY_NOTE` says so on all three surfaces.
2. **Publishing retires the predecessor.** Two rows of the same rule both reading "Published" is
   a library that states two rules and does not say which is in force, so the publish verb moves
   a *published* predecessor to archived in the same transaction. A *draft* predecessor is left
   alone — it was never in force and archiving somebody's work in progress is destructive — and
   an already-archived one is left alone because there is nothing to do. This is the edge the
   contract leaves open, resolved the conservative way and written down here.
3. **No acknowledgement ledger exists.** ``requires_acknowledgment`` is stored and displayed and
   that is all. 6.17 Policy Management & Acknowledgment owns assignment, sign-off and chasing; no
   view here records who read a policy, and nothing is authorized on the flag.
4. **Every refusal is a message and a redirect** — never a 500, never a silent no-op. A verb
   called on a policy already in its target state says so and writes nothing, so a double-click
   cannot re-stamp ``published_at``.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. The ``crud_*``
  helpers enforce it for create/edit/delete; the list and the detail narrow their own base, and
  the publish verb re-narrows the predecessor it may write to (see the WARNING there).
* **``?review=`` is an ALLOW-LIST.** Only ``due`` is recognised; anything else falls through and
  leaves the register alone instead of emptying it (L11) — the same contract ``crud_list`` keeps
  for its own enum filters.
* **``ppolicy_detail`` is hand-rolled rather than ``crud_detail``** — three of its five context
  keys are derived FROM the row (``supersedes``, ``superseded_by_rows``, ``is_review_due``), and
  ``crud_detail``'s ``extra_context`` is built before it fetches, so routing through it would
  mean fetching the same row twice. The tenant scoping and the ``obj`` context name are identical
  to the helper's (the 6.5 ``event_detail`` and the entity-1 ``pdocument_detail`` precedent).
* **The version chain is walked exactly ONE hop in each direction on every page.** ``supersedes``
  is a single FK and ``superseded_by_rows`` a single reverse slice, so no render can be made to
  follow a loop even if one somehow reached the database. Loops are refused at write time by
  ``ProcurementPolicy.clean()`` / ``supersession_conflict``.
"""
from django.db import transaction
from django.db.models import Count, Q

from apps.procurement.forms.DocumentKnowledgeManagement.Policies import ProcurementPolicyForm
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.Policies import (
    ADVISORY_NOTE, ProcurementPolicy)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/documentknowledge/policy/list.html"
TEMPLATE_DETAIL = "procurement/documentknowledge/policy/detail.html"
TEMPLATE_FORM = "procurement/documentknowledge/policy/form.html"

#: What one register ROW renders. Pinned once so the list's select_related and the detail's
#: cannot drift apart. ``threshold_currency`` is in here because ``threshold_label`` reads the
#: currency code — without the hint that is one query per row for a label.
_ROW_RELATIONS = ("applies_to", "owner", "document", "threshold_currency")
#: The detail page additionally names the version it replaces and the author.
_DETAIL_RELATIONS = _ROW_RELATIONS + ("previous_version", "created_by")

#: The review facet. ONE option, and it is an allow-list of one: an unrecognised ``?review=``
#: leaves the register alone rather than emptying it (L11). The label is "Review due", the same
#: words ``EXPIRY_FILTER_CHOICES`` uses on the document register and the same words the badge
#: prints on all three registers — one concept had been reading as two ("due" in amber on one
#: page, "overdue" in red on the next), which teaches a user that the second one is worse.
REVIEW_CHOICES = [("due", "Review due")]

#: How many successors the detail page lists. A policy with more than ten direct successors is
#: already a data problem; the slice is what keeps the panel — and the query behind it — bounded.
SUPERSEDED_BY_CAP = 10


def _policy_qs(request):
    """The register's base queryset, with the one facet ``crud_list`` cannot express.

    ``crud_list``'s ``filters`` tuples compare a GET value against one ORM lookup; the review
    facet is a DATE COMPARISON against today, so it is pre-narrowed here — before ``crud_list``
    paginates, which is the only ordering that gives honest page counts.

    The comparison is exactly the one ``ProcurementPolicy.is_review_due`` makes in Python, so the
    rows this facet returns are precisely the rows that carry the "Review due" badge and are
    counted by the ``review_due`` stat tile.
    """
    qs = (ProcurementPolicy.objects.filter(tenant=request.tenant)
          .select_related(*_ROW_RELATIONS))

    if request.GET.get("review", "").strip() == "due":
        qs = qs.filter(next_review_on__lte=timezone.localdate())
    return qs


def _org_units(tenant):
    """The scope facet's options — this workspace's org units, ordered by name."""
    from apps.core.models import OrgUnit

    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant).order_by("name")


@login_required
def ppolicy_list(request):
    """The policy library register — every written procurement rule in the workspace."""
    base = ProcurementPolicy.objects.filter(tenant=request.tenant)
    today = timezone.localdate()
    # ONE conditional aggregate, not four COUNTs. Computed over the whole workspace, not the
    # filtered page, so the tiles keep meaning something while a facet is applied.
    stats = base.aggregate(
        total=Count("pk"),
        published=Count("pk", filter=Q(status="published")),
        draft=Count("pk", filter=Q(status="draft")),
        # Deliberately the same comparison as the ?review=due facet and the row badge — one
        # definition of "overdue", so the tile and the list can never disagree.
        review_due=Count("pk", filter=Q(next_review_on__lte=today)),
    )
    return crud_list(
        request, _policy_qs(request), TEMPLATE_LIST,
        # The rule as written is searchable: a buyer looks for "three quotes", not for PPOL-00007.
        search_fields=("number", "title", "summary", "body"),
        # policy_type and status are CHOICES strings crud_list enum-guards; org_unit is an FK pk
        # and needs the as_db_int guard (is_int=True) so a hand-edited query string cannot 500
        # the page (L11).
        filters=(("policy_type", "policy_type", False),
                 ("status", "status", False),
                 ("org_unit", "applies_to_id", True)),
        extra_context={
            "policy_type_choices": ProcurementPolicy.POLICY_TYPE_CHOICES,
            "status_choices": ProcurementPolicy.STATUS_CHOICES,
            "org_units": _org_units(request.tenant),
            "review_choices": REVIEW_CHOICES,
            "stats": stats,
            "advisory_note": ADVISORY_NOTE,
        },
    )


@login_required
def ppolicy_detail(request, pk):
    """One policy, the version it replaces, and the versions that replace it.

    Hand-rolled for the reason in the module docstring; the tenant scoping is exactly
    ``crud_detail``'s and the row context key is the same ``obj``.
    """
    obj = get_object_or_404(
        ProcurementPolicy.objects.filter(tenant=request.tenant)
        .select_related(*_DETAIL_RELATIONS), pk=pk)

    # ONE hop each way, and that is the whole traversal this page performs. ``supersedes`` came
    # down with the select_related above, so it costs nothing; the successors are a single
    # bounded reverse slice over local columns (number, title, version_number, status), so no
    # select_related is needed for what the panel renders.
    #
    # WARNING: the reverse slice is re-scoped to this policy's tenant, for the same reason the
    # publish verb below re-fetches its predecessor with an explicit filter. FK traversal bypasses
    # every tenant filter: a ``previous_version_id`` written before the model's cross-tenant
    # backstop existed - or through the admin, or a shell - would print another workspace's
    # number, title, version and status here and link to it. No write path in this codebase
    # creates such a row today, which is what makes this defence in depth rather than a fix;
    # putting the tenancy in the QUERY is what keeps it true whatever writes the column next.
    superseded_by_rows = list(
        obj.superseded_by.filter(tenant_id=obj.tenant_id)[:SUPERSEDED_BY_CAP])

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "advisory_note": ADVISORY_NOTE,
        "supersedes": obj.previous_version,
        "superseded_by_rows": superseded_by_rows,
        # ``is_review_due`` is deliberately NOT lifted into context. It is a property of ``obj``,
        # every register template already reads it as ``obj.is_review_due``, and a context key of
        # the same name meant one fact reachable by two names inside one sub-module.
    })


@login_required
def ppolicy_create(request):
    return crud_create(request, form_class=ProcurementPolicyForm, template=TEMPLATE_FORM,
                       success_url="procurement:ppolicy_list",
                       extra_context={"advisory_note": ADVISORY_NOTE})


@login_required
def ppolicy_edit(request, pk):
    return crud_edit(request, model=ProcurementPolicy, pk=pk,
                     form_class=ProcurementPolicyForm, template=TEMPLATE_FORM,
                     success_url="procurement:ppolicy_list",
                     extra_context={"advisory_note": ADVISORY_NOTE})


@login_required
@tenant_admin_required
@require_POST
def ppolicy_delete(request, pk):
    """Remove a policy nobody has signed. Administrator-gated.

    ``previous_version`` is SET_NULL, so deleting v1.0 leaves v2.0 in force with its back-pointer
    cleared - the history loses a link, never a live rule. There is no stored file to reclaim
    either: a policy's PDF is a ProcurementDocument and stays where it is, still versioned and
    still searchable.

    What DOES cascade is 6.17's acknowledgement ledger. ``PolicyAttestation.policy`` is declared
    ``on_delete=models.CASCADE``, deliberately and by that sub-module, so deleting a published
    policy silently destroys every signature and every exemption grant recorded against it - the
    compliance evidence 6.17 exists to hold. This verb therefore refuses while any attestation
    exists, and only a workspace administrator may call it at all: publishing a rule needs an
    administrator, so unpublishing it by deletion cannot need less. Archiving is the way to
    retire a policy that has history; it keeps the text, the version chain and the sign-offs.
    """
    obj = _get_policy(request, pk)
    signed = obj.attestations.count()
    if signed:
        messages.error(request, f"{obj.number} v{obj.version_number} has {signed} "
                                f"acknowledgement record(s) against it, and deleting the policy "
                                f"would delete them with it. Archive it instead - it keeps its "
                                f"text, its version history and every sign-off.")
        return redirect("procurement:ppolicy_detail", pk=obj.pk)
    return crud_delete(request, model=ProcurementPolicy, pk=pk,
                       success_url="procurement:ppolicy_list")


# ---------------------------------------------------------------------------------------------
# Verbs. Both POST-only, both audited, both redirect back to the policy they acted on. Each one
# refuses a disallowed transition with messages.error, and reports an already-in-target-state
# call with messages.info and NO write, so a double-click cannot re-stamp who and when.
# ---------------------------------------------------------------------------------------------


def _get_policy(request, pk):
    return get_object_or_404(ProcurementPolicy, pk=pk, tenant=request.tenant)


@login_required
@tenant_admin_required
@require_POST
def ppolicy_publish(request, pk):
    """Put a draft policy in force, and retire the version it replaces.

    Administrator-gated: publishing is what makes a rule the workspace's stated position, and it
    is the action that archives another row.

    The refusals, in order:

    * already published -> idempotent ``messages.info`` and **no write**, so a double-click
      cannot move ``published_at`` and make the record claim a later publication date;
    * archived -> **refused**. A retired policy is not re-published in place: it is superseded by
      a new version that points back at it, which is what leaves a readable history. Re-opening
      the archived row instead would silently rewrite what was in force and when.

    Then, under a row lock: stamp ``status`` and ``published_at``, and — the edge the contract
    leaves open, taken the conservative way — archive the predecessor **when the predecessor is
    itself published**. A draft predecessor is untouched (it was never in force, and archiving
    somebody's work in progress is destructive); an archived one is untouched (already done).
    Both writes share one transaction, so a version and the predecessor it names can never be
    left both published, and never both retired. Note the limit of that guarantee: it reaches
    only the predecessor this row POINTS AT. Publish v1.0, then create v2.0 leaving
    ``previous_version`` blank and publish that too, and the library shows two published versions
    of the same title - nothing here can archive a predecessor it was never told about. Linking
    each version to the one it replaces is what makes the chain say which rule is in force.

    The status re-check happens INSIDE the lock because the first one is a read another publish
    can interleave with. Lock order follows the chain — successor first, then predecessor — and
    the chain is acyclic by ``ProcurementPolicy.clean()``, so two concurrent publishes cannot
    take the two locks in opposite orders.
    """
    obj = _get_policy(request, pk)

    if obj.status == "published":
        messages.info(request, f"{obj.number} v{obj.version_number} is already published.")
        return redirect("procurement:ppolicy_detail", pk=obj.pk)
    if obj.status == "archived":
        messages.error(request, f"{obj.number} is archived and cannot be published again. "
                                f"Create the next version and point it back at this one, so the "
                                f"history stays readable.")
        return redirect("procurement:ppolicy_detail", pk=obj.pk)

    retired = None
    raced = False
    with transaction.atomic():
        locked = (ProcurementPolicy.objects.select_for_update()
                  .get(pk=obj.pk, tenant=request.tenant))
        if locked.status != "draft":
            raced = True
        else:
            locked.status = "published"
            locked.published_at = timezone.now()
            locked.save(update_fields=["status", "published_at", "updated_at"])

            # WARNING: the predecessor is re-fetched with an EXPLICIT tenant filter rather than
            # read off ``locked.previous_version``. FK traversal bypasses every tenant filter —
            # ``policy.previous_version`` returns whatever row that column points at, in any
            # workspace — so a ``previous_version_id`` written before the model's cross-tenant
            # backstop existed (or through the admin, or a shell) would let this verb ARCHIVE
            # ANOTHER WORKSPACE'S PUBLISHED POLICY. The secure alternative is exactly this: put
            # the tenancy in the QUERY, so a foreign predecessor is simply not found and cannot
            # be written to. ``select_for_update`` locks it for the same transaction.
            predecessor = None
            if locked.previous_version_id:
                predecessor = (ProcurementPolicy.objects.select_for_update()
                               .filter(pk=locked.previous_version_id,
                                       tenant_id=locked.tenant_id)
                               .first())
            if predecessor is not None and predecessor.status == "published":
                predecessor.status = "archived"
                predecessor.save(update_fields=["status", "updated_at"])
                retired = predecessor
            obj = locked

    if raced:
        messages.info(request, "Another administrator published this policy while the page was "
                               "open. Nothing was changed — reload to see where it stands now.")
        return redirect("procurement:ppolicy_detail", pk=obj.pk)

    write_audit_log(request.user, obj, "policy_publish",
                    {"number": obj.number, "version": obj.version_number,
                     "from": "draft", "to": "published",
                     "superseded": retired.number if retired is not None else None})
    if retired is not None:
        # A second row, against the policy that was retired: whoever reads THAT policy's history
        # has to be able to see why it stopped being in force, and by what.
        write_audit_log(request.user, retired, "policy_superseded",
                        {"number": retired.number, "version": retired.version_number,
                         "from": "published", "to": "archived",
                         "superseded_by": obj.number})

    messages.success(
        request,
        f"{obj.number} v{obj.version_number} is now published."
        + (f" {retired.number} v{retired.version_number} was archived — it is the version this "
           f"one replaces." if retired is not None else "")
        + " Publishing records the rule; it does not change any approval routing.")
    return redirect("procurement:ppolicy_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def ppolicy_archive(request, pk):
    """Retire a policy. Allowed from any state - nothing is deleted.

    Administrator-gated, exactly like publish. "Taking a rule OUT of the library is the safe
    direction" does not survive the asymmetry: publishing needs an administrator because it makes
    a rule the workspace's stated position, and un-making that position changes what every member
    reads as authoritative just as much. It is also not reversible by the person who did it -
    ``ppolicy_publish`` refuses to re-publish an archived row on purpose, so restoring the
    workspace's stated rule means an administrator authoring a new version.

    Nothing is destroyed: the row keeps its text and its version history, and it can be superseded
    by a new version afterwards exactly as before.
    """
    obj = _get_policy(request, pk)
    if obj.status == "archived":
        messages.info(request, f"{obj.number} is already archived.")
        return redirect("procurement:ppolicy_detail", pk=obj.pk)

    previous = obj.status
    obj.status = "archived"
    # ``published_at`` is deliberately LEFT ALONE. It records that this policy was published and
    # when — archiving it later does not un-happen that, and clearing the stamp would erase the
    # only evidence of the period it was in force.
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "policy_archive",
                    {"number": obj.number, "version": obj.version_number,
                     "from": previous, "to": "archived"})
    messages.success(request, f"{obj.number} v{obj.version_number} archived. Nothing was deleted "
                              f"— it keeps its text and its place in the version history.")
    return redirect("procurement:ppolicy_detail", pk=obj.pk)
