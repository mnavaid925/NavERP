"""Inventory 5.4 Receiving & Putaway — PutawayRule + the directed-putaway resolver.

The sub-module's whole brain is ONE configuration table and ONE pure function. A
``PutawayRule`` is a tenant's standing instruction ("VAC-10 arriving at DOCK-1 goes to
CR-01"); :func:`resolve_putaway_suggestion` reads those instructions plus the stock ledger
and answers "which bin?" for a putaway task, or honestly refuses.

The honesty rules this file owns:

* **Every answer carries its reason, citing codes/SKUs only** — an operator reading the
  suggestions queue must see WHY a bin was picked without opening anything else.
* **A refusal starts "No Suggestion Found" — never a guessed bin.** An empty answer the
  user can act on (override the destination by hand) beats a plausible wrong one.
* **On-hand is always the StockMove aggregate**, never stored; blank ``capacity`` means
  UNLIMITED (a bin with no declared limit is never "full"), mirroring 4.3/4.4 semantics.
* **ZERO writes**: the resolver reads scm.Item / scm.Location / scm.StockMove / its own
  rules and writes nothing anywhere. Applying a suggestion stays SCM's job
  (``scm:putawaytask_edit``); Module 5 never moves another app's stock.

Determinism is load-bearing: every candidate stream has a total order (tier DESC →
priority ASC → id ASC for rules; pick_sequence ASC → code ASC for bins), so identical data
resolves to an identical suggestion on every run — no set-iteration accidents, no
timezone-dependent text in any reason string.

Owner-conflict semantics follow 4.17's contamination rule: a location reserved to client X
never holds client Y's goods, while a blank ``owner_client`` is shared space anyone may use.
"""
from apps.inventory.models._base import *  # noqa: F401,F403
# BY NAME from the SCM package root (already wired), never into a sibling's internals:
# Module 5 extends the SCM spine exactly as _base.py documents.
from apps.scm.models import Location, PutawayTask, StockMove

#: Rule specificity tiers — HIGHER wins before priority is even looked at, so a pinned-item
#: rule always out-ranks a category rule which always out-ranks the catch-all.
TIER_ITEM = 3
TIER_CATEGORY = 2
TIER_ANY = 1

#: Location ancestry walks are bounded exactly like ``Location.path()``'s cycle guard: a
#: malformed self-parent row can cost a few hops, not a hung page. 8 covers warehouse › zone
#: › bin plus headroom for intermediate levels nobody has needed yet.
_MAX_ANCESTRY_HOPS = 8

#: Bins without a ``pick_sequence`` sort LAST within their pickable group, deterministically.
_UNSEQUENCED = 10 ** 9


class PutawayRule(TenantOwned):
    """One standing putaway instruction: arriving goods like THIS go to THAT destination.

    Plain configuration — deliberately NO ``[PWR-]`` numbering and no number column: the
    row is read by the resolver, not referenced by other documents, so a human-readable
    identity would be a second thing to keep meaningful.

    Overlapping rules are LEGAL (no unique_together): "all chilled items → chilled zone"
    and "MON-27 → WH-MAIN-A1" can both exist, and the resolver's tier order decides which
    fires. Specificity beats priority beats age — item (tier 3) over category (tier 2)
    over catch-all (tier 1).
    """

    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_putaway_rules",
        help_text="Exact-item match (most specific tier); leave blank for broader rules")
    category = models.ForeignKey(
        "scm.ItemCategory", on_delete=models.PROTECT, null=True, blank=True,
        related_name="category_putaway_rules",
        help_text="Category match (middle tier); ignored when an item is pinned")
    source_location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="putaway_rules_from",
        help_text="Applies when goods arrive in this staging/dock; blank = any arrival point")
    destination = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, related_name="putaway_rules_to",
        help_text="Destination bin or zone")
    priority = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["priority", "id"]
        # NO unique_together by design — overlapping rules are how a warehouse expresses
        # fallbacks. The resolver order, not a constraint, decides which rule applies.
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="inv_pwr_tnt_active_idx"),
        ]

    def clean(self):
        """Per-field cross-tenant rejection (keyed on the field, so it renders where the
        user is looking) + the same-location sanity check as PutawayTask.clean()."""
        super().clean()
        errors = {}
        for name in ("item", "category", "source_location", "destination"):
            # Key off the raw ``<name>_id``, never attribute access: a crafted or incomplete
            # POST (foreign pk removed from cleaned_data, destination omitted entirely)
            # leaves a required FK unassigned here, and reading it then raises
            # RelatedObjectDoesNotExist — which is not a ValidationError and would escape
            # full_clean() as an unhandled 500 instead of a form error. Unset = nothing to
            # reject; the form's own required/field errors cover those cases.
            if getattr(self, f"{name}_id") is None:
                continue
            chosen = getattr(self, name)
            if chosen.tenant_id != self.tenant_id:
                errors[name] = "That record belongs to another workspace."
        if self.source_location_id and self.source_location_id == self.destination_id:
            errors["__all__"] = "Source and destination must be different locations."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        if self.item_id:
            scope = self.item.sku
        elif self.category_id:
            scope = self.category.name
        else:
            scope = "Any item"
        dest = self.destination.code if self.destination_id else "?"
        return f"{scope} → {dest}"


def _ancestor_chain(location, by_pk):
    """``[location, parent, grandparent, …]`` resolved through the preloaded map — one hop
    of dict lookup, zero queries — bounded by the same cycle guard as ``Location.path()``."""
    chain, node, seen = [], location, set()
    while node is not None and node.pk not in seen and len(chain) <= _MAX_ANCESTRY_HOPS:
        seen.add(node.pk)
        chain.append(node)
        node = by_pk.get(node.parent_id) if node.parent_id else None
    return chain


def _nearest_condition(chain):
    """The nearest own-or-ancestor non-blank storage condition: ``(value, node)`` or
    ``(None, None)`` when the whole chain is ambient/unclassified. Nearest wins — a bin's
    own classification outranks its zone's, which outranks the warehouse's."""
    for node in chain:
        if node.storage_condition:
            return node.storage_condition, node
    return None, None


def _walk_key(location):
    """Total walk order for bins, per the frozen contract: pick_sequence ASC then code ASC.
    Bins without a ``pick_sequence`` sort LAST, deterministically (_UNSEQUENCED); no
    pickable/unpickable group flag — tiers that need one filter it before sorting."""
    return (location.pick_sequence if location.pick_sequence is not None else _UNSEQUENCED,
            location.code)


def resolve_putaway_suggestion(task, *, rules=None, by_pk=None, on_hand=None):
    """Rank putaway destinations for one open ``PutawayTask``.

    Returns ``(suggestion_or_None, reason_str, candidates)`` where ``candidates`` is the
    ranked best-first list of ``(location, reason_str)`` pairs and, when non-empty,
    ``candidates[0]`` IS the suggestion. An empty list comes back with a reason starting
    ``"No Suggestion Found"`` — rendered verbatim by the queue page, never replaced by a
    guess.

    Tier order is FROZEN: matching active rules (item > category > catch-all), then bins
    already holding the item, then storage-condition matches, then walk-order fallback.
    The same disqualifiers guard every tier: an inactive location, a full bin (declared
    capacity reached — blank capacity is unlimited), a client-dedicated bin that belongs to
    someone else's goods, and the staging location itself.

    Cost modes: called bare (direct tests, single-task callers) the resolver self-loads
    three bounded inputs — active rules, the item's per-location ledger aggregate, the
    tenant's location map. Queue pages instead PRELOAD all three once per request and pass
    them in (``rules=…``, ``by_pk=…``, ``on_hand={item_id: {location_id: qty}}``), which
    skips those internal fetches entirely and keeps a whole-backlog render flat-cost;
    keyword-only args, so positional callers are unaffected either way. The ancestry-chain
    cache derives from whichever ``by_pk`` map is in scope — dict hops, zero queries.
    """
    item = task.item

    # Tenancy guard, cheap and FIRST: today every write path keeps task.tenant ==
    # task.item.tenant, but nothing structural forces it — a future non-form writer could
    # hang a foreign item off a task and poison every reason string below with another
    # workspace's SKUs. Refuse honestly rather than route on borrowed data.
    if item is not None and item.tenant_id != task.tenant_id:
        return None, ("No Suggestion Found: this task's item belongs to another "
                      "workspace; fix the tenancy mismatch before routing it."), []

    # --- shared inputs (each self-loaded only when the caller didn't preload it) ---------
    # On-hand per location for THIS item straight off the append-only ledger. One GROUP BY
    # feeds the consolidation tier AND every full-bin check below.
    if on_hand is None:
        on_hand_at = dict(
            StockMove.objects.filter(tenant=task.tenant_id, item_id=item.pk)
            .values("location").annotate(held=Sum("quantity")).values_list("location", "held"))
    else:
        on_hand_at = on_hand.get(item.pk) or {}
    # Every location once, parents resolvable in memory: turns each ancestry walk into dict
    # lookups instead of a query-per-hop (the N+1 a naive .parent walk would do per task).
    if by_pk is None:
        by_pk = {loc.pk: loc for loc in Location.objects.filter(tenant=task.tenant_id)}
    chains = {}

    def chain_of(loc):
        got = chains.get(loc.pk)
        if got is None:
            got = chains[loc.pk] = _ancestor_chain(loc, by_pk)
        return got

    def disqualified(loc):
        """True when a candidate may NOT take this arrival — identical bar in every tier."""
        held = on_hand_at.get(loc.pk)
        return (
            not loc.is_active
            or loc.pk == task.from_location_id
            # Full only against a DECLARED capacity: blank capacity is unlimited, never zero.
            or (loc.capacity is not None and (held or ZERO) >= loc.capacity)
            # 4.17 contamination rule: reserved space never takes another client's goods;
            # blank owner_client is shared space anyone may use.
            or (loc.owner_client_id is not None and loc.owner_client_id != item.owner_client_id)
        )

    candidates, seen_pks = [], set()

    def offer(loc, reason):
        if loc.pk not in seen_pks and not disqualified(loc):
            seen_pks.add(loc.pk)
            candidates.append((loc, reason))

    # --- tier 1: matching active rules ---------------------------------------------------
    matched = []
    rule_stream = rules
    if rule_stream is None:
        rule_stream = (PutawayRule.objects.filter(tenant=task.tenant_id, is_active=True)
                       .select_related("item", "category", "source_location", "destination"))
    for rule in rule_stream:
        # A rule scoped to an arrival point fires only for goods actually sitting there.
        if rule.source_location_id is not None and rule.source_location_id != task.from_location_id:
            continue
        if rule.item_id == item.pk:
            tier, scope = TIER_ITEM, rule.item.sku
        elif rule.item_id is None and rule.category_id == item.category_id and rule.category_id is not None:
            tier, scope = TIER_CATEGORY, rule.category.name
        elif rule.item_id is None and rule.category_id is None:
            tier, scope = TIER_ANY, "Any item"
        else:
            continue
        matched.append(((-tier, rule.priority, rule.id), rule, scope))
    matched.sort(key=lambda entry: entry[0])
    for _key, rule, scope in matched:
        # Walk DOWN the ranking past a disqualified destination rather than refusing
        # outright: the next-best rule is still a deterministic, explainable answer.
        dest = rule.destination
        if dest.pk in by_pk:  # by_pk guard = same tenant; the rest is offer()'s job
            arriving = f" arriving {rule.source_location.code}" if rule.source_location_id else ""
            offer(dest, f"Rule: {scope}{arriving} → {dest.code}")

    # --- tier 2: consolidation — bins already holding this item ---------------------------
    holding_bins = [loc for pk, loc in by_pk.items()
                    if loc.location_type == "bin" and (on_hand_at.get(pk) or ZERO) > ZERO]
    holding_bins.sort(key=_walk_key)
    for loc in holding_bins:
        offer(loc, f"Already holds {item.sku}")

    # --- tier 3: storage-condition match --------------------------------------------------
    needed = item.storage_condition
    if needed:
        condition_bins = []
        for loc in by_pk.values():
            if loc.location_type != "bin":
                continue
            value, node = _nearest_condition(chain_of(loc))
            if value == needed:
                condition_bins.append((loc, node))
        condition_bins.sort(key=lambda pair: _walk_key(pair[0]))
        for loc, node in condition_bins:
            offer(loc, f"Condition '{needed}' matched at {node.code}")

    # --- tier 4: walk-order fallback under the receipt's warehouse -------------------------
    warehouse = next((node for node in chain_of(task.from_location)
                      if node.location_type == "warehouse"), None)
    if warehouse is not None:
        fallback_bins = []
        for loc in by_pk.values():
            if loc.location_type != "bin" or not loc.is_pickable:
                continue
            if warehouse.pk not in {node.pk for node in chain_of(loc)}:
                continue
            fallback_bins.append(loc)
        fallback_bins.sort(key=_walk_key)
        for loc in fallback_bins:
            offer(loc, "First pickable bin by walk order")

    if not candidates:
        return None, ("No Suggestion Found: no active rule matched this arrival and no "
                      "eligible bin passed the free-capacity and ownership checks."), []
    suggestion, reason = candidates[0]
    return suggestion, reason, candidates


# Re-exported so the integrate phase's single package-root line covers the whole brain:
#   from .ReceivingPutaway.PutawayRules import PutawayRule, resolve_putaway_suggestion
__all__ = ["PutawayRule", "resolve_putaway_suggestion", "TIER_ANY", "TIER_CATEGORY", "TIER_ITEM"]
