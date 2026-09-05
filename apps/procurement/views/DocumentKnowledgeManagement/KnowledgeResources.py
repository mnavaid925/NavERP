"""Procurement 6.19 Document & Knowledge Management — KnowledgeResource views.

The **Best Practices & Templates** bullet: the register (search, five facets, the featured shelf,
pagination), detail, create, edit, delete — plus three POST-only verbs: publish, archive and
"use this".

The rules this module enforces, because they are what the library is for:

1. **A resource is content, not machinery.** Nothing here executes anything stored on a row. The
   requisition templates that actually raise a purchase are 6.2's, the RFx questionnaire builder
   is 6.6's and the clause library is 6.8's; this library links to them. :data:`LIBRARY_NOTE`
   says so on all three surfaces.
2. **The use counter is atomic.** ``knowledgeresource_use`` increments with an
   ``F("usage_count") + 1`` expression, so the read and the write happen in ONE ``UPDATE`` inside
   the database. Two people opening the same playbook in the same second both count. A Python
   ``obj.usage_count += 1`` would read 4 twice and write 5 twice, and the library would quietly
   under-report exactly the resources people use most — the ones with concurrent readers.
3. **The counter is a counter, not a ledger.** It records that the button was pressed, not who
   pressed it or what they did next. The per-press ``write_audit_log`` row is what can answer
   "who", and a per-user usage ledger is 6.17 / Module 13 territory — there is no such model
   here and this module builds none.
4. **Publish and archive are NOT administrator-gated**, unlike ``ppolicy_publish``. Publishing a
   policy states the workspace's binding rule and retires another row; publishing a guide adds a
   how-to to a shelf and retires nothing. Gating it would put the person who wrote the guidance
   behind the person who administers the workspace for no safety gained. The gate that does apply
   is the one that always applies: ``@login_required`` plus ``filter(tenant=request.tenant)``.
5. **Every refusal is a message and a redirect** — never a 500, never a silent no-op. A verb
   called on a resource already in its target state says so and writes nothing.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. The ``crud_*``
  helpers enforce it for create/edit/delete; the list, the shelf and the detail narrow their own
  base.
* **The ordering is deterministic.** ``KnowledgeResource.Meta.ordering`` is
  ``["-is_featured", "-created_at", "-id"]`` and no view re-orders the register, so the featured
  rows lead and the unique ``id`` breaks every remaining tie. An unstable sort under a Paginator
  repeats one row on page 2 and drops another; the ``id`` tiebreak is what makes paging honest.
* **The featured shelf is computed separately and is NOT paginated** — it is capped at
  ``FEATURED_CAP`` rows, published-and-featured only, so page 3 of the register still shows the
  same "start here" shelf as page 1.
* **``knowledgeresource_detail`` is hand-rolled rather than ``crud_detail``** — two of its four
  context keys are derived FROM the row (``document``, ``is_review_due``), and ``crud_detail``'s
  ``extra_context`` is built before it fetches, so routing through it would mean fetching the
  same row twice. The tenant scoping and the ``obj`` context name are identical to the helper's
  (the entity-1 ``pdocument_detail`` and entity-3 ``ppolicy_detail`` precedent).
"""
# ``F`` is imported here EXPLICITLY: the views star-import surface (views/_common.py) carries the
# shortcuts, the decorators and the crud_* helpers but no ORM expressions, and the models star
# surface that does carry F belongs to a different package. The atomic use-counter increment in
# ``knowledgeresource_use`` depends on it.
from django.db.models import Count, F, Q

from apps.procurement.forms.DocumentKnowledgeManagement.KnowledgeResources import (
    KnowledgeResourceForm)
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.KnowledgeResources import (
    FEATURED_CAP, LIBRARY_NOTE, KnowledgeResource)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/documentknowledge/knowledgeresource/list.html"
TEMPLATE_DETAIL = "procurement/documentknowledge/knowledgeresource/detail.html"
TEMPLATE_FORM = "procurement/documentknowledge/knowledgeresource/form.html"

#: What one register ROW renders. Pinned once so the list's select_related, the shelf's and the
#: detail's cannot drift apart.
_ROW_RELATIONS = ("owner", "document")
#: The detail page additionally names the author.
_DETAIL_RELATIONS = _ROW_RELATIONS + ("created_by",)

#: The featured facet. EXACTLY the strings ``crud_list`` maps to booleans ("True"/"False") — any
#: other value raises inside ``.filter()`` and is skipped, which is the behaviour that keeps a
#: hand-edited query string from emptying the register (L11).
FEATURED_CHOICES = [("True", "Featured only"), ("False", "Not featured")]


def _resource_qs(request):
    """The register's base queryset.

    No pre-narrow is needed here — every facet this register offers is expressible as a
    ``crud_list`` filter tuple, so all five are declared there and applied before pagination.
    Ordering is the model's own (featured, newest, id), deliberately not re-stated: one
    definition of the shelf order means the register, the shelf and every page of the paginator
    agree.
    """
    return (KnowledgeResource.objects.filter(tenant=request.tenant)
            .select_related(*_ROW_RELATIONS))


def _featured_shelf(tenant):
    """The "start here" shelf — published, featured, capped, and NOT paginated.

    Computed separately from the register on purpose: the shelf answers "where do I start?" and
    must read the same on page 3 as on page 1, which a slice of the paginated queryset would not.
    The cap is what keeps this one extra query bounded however many rows somebody stars.
    """
    if tenant is None:
        return []
    return list(KnowledgeResource.objects
                .filter(tenant=tenant, status="published", is_featured=True)
                .select_related(*_ROW_RELATIONS)[:FEATURED_CAP])


@login_required
def knowledgeresource_list(request):
    """The shared library register — every template, scorecard and playbook in the workspace."""
    base = KnowledgeResource.objects.filter(tenant=request.tenant)
    # ONE conditional aggregate, not four COUNTs. Computed over the whole workspace, not the
    # filtered page, so the tiles keep meaning something while a facet is applied.
    stats = base.aggregate(
        total=Count("pk"),
        published=Count("pk", filter=Q(status="published")),
        featured=Count("pk", filter=Q(is_featured=True)),
        # How many resources anybody has ever reached for — the count of ROWS with a press, not
        # the sum of presses. "12 of 40 guides have been opened" is a fact about the library;
        # a total press count would say more about one popular playbook than about the shelf.
        used=Count("pk", filter=Q(usage_count__gt=0)),
    )
    return crud_list(
        request, _resource_qs(request), TEMPLATE_LIST,
        # The guidance itself is searchable: a buyer looks for "escalation clause", not PKR-00007.
        search_fields=("number", "title", "summary", "body", "tags"),
        # All five are CHOICES/boolean columns crud_list guards for itself — the four enums by
        # its choices allow-list, is_featured by the "True"/"False" mapping plus the
        # ValueError/ValidationError catch — so a hand-edited query string skips the facet
        # instead of emptying the register (L11).
        filters=(("resource_type", "resource_type", False),
                 ("category", "category", False),
                 ("audience", "audience", False),
                 ("status", "status", False),
                 ("featured", "is_featured", False)),
        extra_context={
            "resource_type_choices": KnowledgeResource.RESOURCE_TYPE_CHOICES,
            "category_choices": KnowledgeResource.CATEGORY_CHOICES,
            "audience_choices": KnowledgeResource.AUDIENCE_CHOICES,
            "status_choices": KnowledgeResource.STATUS_CHOICES,
            "featured_choices": FEATURED_CHOICES,
            "featured": _featured_shelf(request.tenant),
            "stats": stats,
            "library_note": LIBRARY_NOTE,
        },
    )


@login_required
def knowledgeresource_detail(request, pk):
    """One resource, its guidance text and the artifact it points at.

    Hand-rolled for the reason in the module docstring; the tenant scoping is exactly
    ``crud_detail``'s and the row context key is the same ``obj``.
    """
    obj = get_object_or_404(
        KnowledgeResource.objects.filter(tenant=request.tenant)
        .select_related(*_DETAIL_RELATIONS), pk=pk)

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "library_note": LIBRARY_NOTE,
        # Came down with the select_related above, so naming it costs nothing and the template
        # reads one name instead of hopping through the object for a nullable relation.
        "document": obj.document,
        # The model property lifted into context under the name the contract pins.
        "is_review_due": obj.is_review_due,
    })


@login_required
def knowledgeresource_create(request):
    return crud_create(request, form_class=KnowledgeResourceForm, template=TEMPLATE_FORM,
                       success_url="procurement:knowledgeresource_list",
                       extra_context={"library_note": LIBRARY_NOTE})


@login_required
def knowledgeresource_edit(request, pk):
    return crud_edit(request, model=KnowledgeResource, pk=pk,
                     form_class=KnowledgeResourceForm, template=TEMPLATE_FORM,
                     success_url="procurement:knowledgeresource_list",
                     extra_context={"library_note": LIBRARY_NOTE})


@login_required
@require_POST
def knowledgeresource_delete(request, pk):
    # Nothing cascades. ``document`` is SET_NULL on the other side of the relation — deleting a
    # resource never touches the file it pointed at, which stays in the repository with its
    # revisions, its approval and its text. What is lost is the guidance written around it.
    return crud_delete(request, model=KnowledgeResource, pk=pk,
                       success_url="procurement:knowledgeresource_list")


# ---------------------------------------------------------------------------------------------
# Verbs. All POST-only, all audited, all redirect back to the resource they acted on. Each one
# refuses a disallowed transition with messages.error, and reports an already-in-target-state
# call with messages.info and NO write, so a double-click cannot re-stamp who and when.
# ---------------------------------------------------------------------------------------------


def _get_resource(request, pk):
    return get_object_or_404(KnowledgeResource, pk=pk, tenant=request.tenant)


@login_required
@require_POST
def knowledgeresource_publish(request, pk):
    """Put a resource on the shelf where colleagues can find it.

    Deliberately NOT administrator-gated — see rule 4 in the module docstring. Publishing a guide
    adds a how-to to a library; it retires nothing, states no binding rule and grants no
    permission. Unlike a policy, an archived resource may be published again: guidance comes back
    into use when practice comes back around, and there is no "what was in force when" record to
    rewrite by doing so.
    """
    obj = _get_resource(request, pk)

    if obj.status == "published":
        messages.info(request, f"{obj.number} is already published.")
        return redirect("procurement:knowledgeresource_detail", pk=obj.pk)

    previous = obj.status
    obj.status = "published"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "knowledge_resource_publish",
                    {"number": obj.number, "title": obj.title,
                     "from": previous, "to": "published"})
    messages.success(request, f"{obj.number} is published and will show in the library. It is "
                              f"guidance for people to read — publishing it changes no workflow "
                              f"and enforces nothing.")
    return redirect("procurement:knowledgeresource_detail", pk=obj.pk)


@login_required
@require_POST
def knowledgeresource_archive(request, pk):
    """Take a resource off the shelf. Allowed from any state — nothing is deleted.

    The row keeps its text, its tags and its usage count, and it can be published again later.
    A linked document is untouched: the file stays in the repository, still versioned and still
    searchable.
    """
    obj = _get_resource(request, pk)
    if obj.status == "archived":
        messages.info(request, f"{obj.number} is already archived.")
        return redirect("procurement:knowledgeresource_detail", pk=obj.pk)

    previous = obj.status
    obj.status = "archived"
    # ``is_featured`` is deliberately LEFT ALONE. The shelf query already requires
    # status="published", so an archived row cannot reach it; clearing the star as well would
    # silently lose the curator's choice when the resource is published again.
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "knowledge_resource_archive",
                    {"number": obj.number, "title": obj.title,
                     "from": previous, "to": "archived"})
    messages.success(request, f"{obj.number} archived. Nothing was deleted — it keeps its text "
                              f"and its usage count, and it can be published again.")
    return redirect("procurement:knowledgeresource_detail", pk=obj.pk)


@login_required
@require_POST
def knowledgeresource_use(request, pk):
    """Record that somebody reached for this resource, and send them to it.

    **The increment is atomic.** ``F("usage_count") + 1`` is evaluated by the DATABASE inside a
    single ``UPDATE … SET usage_count = usage_count + 1``, so the read and the write are one
    operation and no lock is needed. The read-modify-write this replaces —
    ``obj.usage_count += 1; obj.save()`` — reads the old value into Python first, so two people
    opening the same playbook in the same second both read 4 and both write 5, and the library
    quietly under-counts exactly the resources people use most. ``refresh_from_db`` afterwards is
    what turns the expression object back into the real post-increment number, so the audit row
    and the message report what the database actually holds rather than a stale local copy.

    Archived is refused: a resource taken off the shelf is not "in use", and letting the counter
    move on it would make the one number this model keeps mean two different things.

    WARNING: this verb redirects to the resource's own detail page, never to the linked
    document's ``FileField`` URL. A redirect target derived from stored data is an open-redirect
    hop — a ``file.url`` is attacker-influenceable through whatever wrote the row, and
    ``redirect()`` will happily send the browser to an absolute URL it finds there. The secure
    alternative is exactly what is done here: redirect to a route this app reversed itself, and
    let the detail page offer the download as an ordinary link the user can see before they
    click. One extra click removes the entire surface.
    """
    obj = _get_resource(request, pk)

    if obj.status == "archived":
        messages.error(request, f"{obj.number} is archived, so it is not counted as in use. "
                                f"Publish it again if this guidance is back in circulation.")
        return redirect("procurement:knowledgeresource_detail", pk=obj.pk)

    obj.usage_count = F("usage_count") + 1
    obj.last_used_at = timezone.now()
    obj.save(update_fields=["usage_count", "last_used_at", "updated_at"])
    # The attribute is a CombinedExpression until this call replaces it with the stored integer —
    # without the refresh the audit row below would log "F(usage_count) + Value(1)".
    obj.refresh_from_db(fields=["usage_count"])

    # The counter cannot say WHO; this row can. That is the division of labour, and it is why the
    # column above is never read as evidence.
    write_audit_log(request.user, obj, "knowledge_resource_used",
                    {"usage_count": obj.usage_count})
    messages.success(request, f"Noted — {obj.number} has now been used {obj.usage_count} time(s). "
                              f"The count is a tally of this button, nothing more.")
    return redirect("procurement:knowledgeresource_detail", pk=obj.pk)
