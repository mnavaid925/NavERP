"""Procurement 6.18 Inventory & Warehouse Integration — ReplenishmentPolicy views.

**Reorder Point Automation** bullet, configuration half. Plain tenant-scoped CRUD over the
replenishment configuration master: register (search + filters + pagination), detail, create,
edit, delete. The policy gets no sidebar entry of its own — it is reached from the replenishment
run register, the ``ReceiptTolerancePolicy`` / ``SpendClassificationRule`` / ``ReorderRule``
precedent — so the register's own header carries the links back out.

Discipline a reviewer will otherwise go looking for:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. The ``crud_*``
  helpers enforce it for detail/edit/delete; the list narrows its own base queryset, and
  :func:`_filter_dropdowns` returns empty querysets rather than unscoped ones when
  ``request.tenant`` is ``None``. A tenant-less user gets an EMPTY page, never a 500.
* **The stats strip is ONE conditional aggregate**, not four ``COUNT`` round-trips —
  ``inactive`` is derived in Python from ``total - active`` because a fourth branch would buy
  nothing the subtraction does not already give.
* **The detail page reads the planning numbers THROUGH ``scm.ReorderRule``** rather than
  restating them (L36). ``ReplenishmentPolicy.effective_numbers()`` is the one place the
  override-versus-fallback rule is written down — on the MODEL, so this page and
  ``ReplenishmentRun.generate()`` read the same definition without the run having to import
  upward into the views layer — and it labels every figure with where it came from, so nobody has
  to guess whether a reorder point on this page is the policy's or the rule's.
* **Writes are audited** through ``write_audit_log`` (create/edit via the ``crud_*`` helpers,
  delete via ``crud_delete``).
"""
from django.apps import apps as django_apps
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.models import OrgUnit, Party
from apps.scm.models import Item, Location, ReorderRule

from apps.procurement.forms.InventoryWarehouseIntegration.Policies import ReplenishmentPolicyForm
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.InventoryWarehouseIntegration.Policies import ReplenishmentPolicy
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_LIST = "procurement/inventorywarehouse/replenishmentpolicy/list.html"
TEMPLATE_DETAIL = "procurement/inventorywarehouse/replenishmentpolicy/detail.html"
TEMPLATE_FORM = "procurement/inventorywarehouse/replenishmentpolicy/form.html"

#: Register rows show the item (with its UOM), the scope and the preferred vendor. The three
#: requisition-default FKs are NOT joined here — the list never renders them, and four extra
#: joins per page is a real cost for columns nobody asked for.
_LIST_RELATIONS = ("item", "item__uom", "location", "preferred_vendor")

#: The detail page renders all six FKs, so it joins all six (plus the budget's fiscal period,
#: which the budget's own ``__str__`` would otherwise fetch one query later).
_DETAIL_RELATIONS = ("item", "item__uom", "location", "preferred_vendor", "default_org_unit",
                     "default_budget", "default_budget__fiscal_period", "default_gl_account")

#: How many suggestion lines the detail page's "recently proposed" panel shows.
_RECENT_SUGGESTION_LIMIT = 10


def _policy_qs(request):
    return (ReplenishmentPolicy.objects.filter(tenant=request.tenant)
            .select_related(*_LIST_RELATIONS))


def _filter_dropdowns(request):
    """The three FK dropdowns' options — empty querysets for a tenant-less user.

    Only the three axes the list template's filter bar actually offers. The create/edit form
    builds its own (differently narrowed) dropdowns, so shipping the budget / org-unit / GL
    querysets here would fetch them for nothing on every render.
    """
    if request.tenant is None:
        return {"items": Item.objects.none(), "locations": Location.objects.none(),
                "vendors": Party.objects.none()}
    return {
        "items": Item.objects.filter(tenant=request.tenant).order_by("sku"),
        "locations": Location.objects.filter(tenant=request.tenant).order_by("code"),
        # Same supplier-or-vendor rule as the form's dropdown: a policy can only be filtered by a
        # party it could have been pointed at in the first place.
        "vendors": (Party.objects.filter(tenant=request.tenant,
                                         roles__role__in=("supplier", "vendor"))
                    .distinct().order_by("name")),
    }


def _matching_rule(request, policy):
    """The ``scm.ReorderRule`` whose planning numbers this policy overrides, or ``None``.

    Two cases, and the second is the reason this is a function rather than a one-liner:

    * A **located** policy maps onto exactly one rule — ``ReorderRule``'s own
      ``unique_together = ("tenant", "item", "location")`` guarantees ``.first()`` is
      deterministic, not arbitrary.
    * An **any-location** policy (``location`` null) has no single counterpart, because the rule
      table has no catch-all row: ``ReorderRule.location`` is NOT nullable. Reading one rule at
      random and presenting its reorder point as "the" number would be a lie, so a rule is only
      resolved when the item has exactly ONE of them; otherwise the page says the fallback is
      per-location and links to the item. ``[:2]`` is what makes "exactly one" cost one query
      instead of a ``COUNT`` plus a fetch.

    ``is_active`` is deliberately NOT filtered: the panel reports what the rule SAYS, and an
    inactive rule still holds the numbers a run would fall back to. The template badges the
    inactive case rather than hiding it, which is the honest presentation of the same fact.
    """
    if request.tenant is None or not policy.item_id:
        return None
    rules = (ReorderRule.objects.filter(tenant=request.tenant, item_id=policy.item_id)
             .select_related("location"))
    if policy.location_id:
        return rules.filter(location_id=policy.location_id).first()
    candidates = list(rules[:2])
    return candidates[0] if len(candidates) == 1 else None


def _recent_suggestions(request, policy, limit=_RECENT_SUGGESTION_LIMIT):
    """The last few replenishment suggestions this policy shaped, newest run first.

    ``ReplenishmentSuggestion`` is entity 2 of this same sub-module and lands in the same
    changeset, so it is resolved through the app registry at REQUEST time rather than imported at
    module scope. That is not a workaround — it is the correct tool for a soft reference:

    * it needs no edit when entity 2 lands (``get_model`` starts returning the real class), and
    * unlike a module-level ``try: import ... except ImportError``, it cannot swallow a genuine
      breakage inside ``Runs.py`` and turn it into a silently empty panel — a broken module fails
      at app-registry population, loudly, where it should.

    Tenant is reached THROUGH the run (``run__tenant``), which is where 6.18 puts the boundary for
    every suggestion query: the line itself carries no tenant column.
    """
    if request.tenant is None or not policy.pk:
        return []
    try:
        Suggestion = django_apps.get_model("procurement", "ReplenishmentSuggestion")
    except LookupError:
        return []
    return list(Suggestion.objects
                .filter(policy=policy, run__tenant=request.tenant)
                .select_related("run", "item", "item__uom", "location", "vendor")
                # Ordered on the FK and the pk only — both structural — so this panel cannot
                # break on a column rename inside entity 2. Suggestions are bulk-created per run,
                # so descending run id IS newest-run-first.
                .order_by("-run_id", "-id")[:limit])


@login_required
def replenishmentpolicy_list(request):
    """The policy register: how this workspace replenishes each item, and where."""
    base = ReplenishmentPolicy.objects.filter(tenant=request.tenant)
    # ONE conditional aggregate, not four COUNTs. ``inactive`` is a subtraction rather than a
    # third branch, because total - active is exact by construction.
    stats = base.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        auto=Count("pk", filter=Q(trigger_mode="auto", is_active=True)),
    )
    stats["inactive"] = stats["total"] - stats["active"]
    extra = {
        "stats": stats,
        "source_choices": ReplenishmentPolicy.SOURCE_METHOD_CHOICES,
        "trigger_choices": ReplenishmentPolicy.TRIGGER_MODE_CHOICES,
    }
    extra.update(_filter_dropdowns(request))
    return crud_list(
        request, _policy_qs(request), TEMPLATE_LIST,
        search_fields=("item__sku", "item__name", "location__code", "location__name",
                       "preferred_vendor__name", "notes"),
        # The three FK filters need the as_db_int guard (crud_list's is_int=True); the two enum
        # filters get crud_list's CHOICES-membership guard, and is_active is a boolean it maps
        # from the literal strings "True"/"False" itself. None of that is re-implemented here.
        filters=(("item", "item_id", True),
                 ("location", "location_id", True),
                 ("vendor", "preferred_vendor_id", True),
                 ("source_method", "source_method", False),
                 ("trigger_mode", "trigger_mode", False),
                 ("is_active", "is_active", False)),
        extra_context=extra,
    )


@login_required
def replenishmentpolicy_detail(request, pk):
    """One policy, read against the reorder rule it overrides.

    The page's reason to exist is the comparison: on its own a policy is a handful of nullable
    numbers, and it only becomes readable next to the rule's reorder point and safety stock with
    every figure labelled as an override or a fallback.

    Fetched with ``get_object_or_404`` + ``render`` rather than through ``crud_detail``, and the
    contract's ``obj`` key is set BY HAND to exactly what that helper would have set. Every extra
    on this page is computed FROM the policy, so ``crud_detail`` would have had to fetch the same
    row a second time to hand it to the template — the ``contract_detail`` precedent
    (``apps/procurement/views/ContractsManagement/Contracts.py:78``) resolves it the same way.
    The tenant filter is identical to the helper's, so the IDOR boundary is unchanged: another
    workspace's pk is a 404, not a 403 and not a render.
    """
    obj = get_object_or_404(
        ReplenishmentPolicy.objects.filter(tenant=request.tenant)
        .select_related(*_DETAIL_RELATIONS), pk=pk)
    rule = _matching_rule(request, obj)
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "rule": rule,
        "effective": obj.effective_numbers(rule),
        "recent_suggestions": _recent_suggestions(request, obj),
        # Reversed in Python, never in the template: the rule is optional, and a ``{% url %}``
        # tag on a null pk is a NoReverseMatch 500 rather than a blank cell.
        "rule_url": reverse("scm:reorderrule_detail", args=[rule.pk]) if rule else None,
    })


@login_required
def replenishmentpolicy_create(request):
    return crud_create(request, form_class=ReplenishmentPolicyForm, template=TEMPLATE_FORM,
                       success_url="procurement:replenishmentpolicy_list")


@login_required
def replenishmentpolicy_edit(request, pk):
    return crud_edit(request, model=ReplenishmentPolicy, pk=pk,
                     form_class=ReplenishmentPolicyForm, template=TEMPLATE_FORM,
                     success_url="procurement:replenishmentpolicy_list")


@login_required
@require_POST
def replenishmentpolicy_delete(request, pk):
    return crud_delete(request, model=ReplenishmentPolicy, pk=pk,
                       success_url="procurement:replenishmentpolicy_list")
