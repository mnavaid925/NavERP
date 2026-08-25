"""Inventory 5.20 Units of Measure (UOM) — the N:N conversion matrix.

**Ownership (L36/L29):** the UOM MASTER is SCM 4.3's ``scm.UOM`` (code/name/factor,
unique per-tenant code). Its own docstring defers "a full N:N conversion matrix" to a
later slice — THIS is that deferred piece: the standing rules that say 1 Case = 12
Units and 1 Pallet = 40 Cases, held per item or tenant-wide, plus the shared resolver
that turns a quantity in one unit into another — directly, or through a chain of hops
when no single rule joins the pair.

Zero writes into SCM: a conversion is CONFIGURATION around the master, exactly as 5.4's
PutawayRule is configuration around Location. Nothing here touches StockMove —
converting units on paper moves no stock.
"""
from collections import deque
from decimal import Decimal, InvalidOperation

from apps.inventory.models._base import *  # noqa: F401,F403

#: Longest conversion chain the resolver will walk (Pallet → Case → Box → Each is 3).
#: A cap keeps a pathological rule graph from turning the BFS unbounded; five hops is
#: generous for real packaging hierarchies and refuses everything sillier.
MAX_PATH_DEPTH = 5

#: Quantum every derived figure is rounded to — matches ``factor``'s own scale so a
#: chained product (two 14,4 factors ⇒ up to 8 dp) still lands inside the columns
#: downstream forms expect.
RESULT_QUANTUM = Decimal("0.0001")


class UomConversion(TenantOwned):
    """One directed conversion rule: one FROM-unit holds FACTOR TO-units.

    Plain configuration — deliberately NO numbering (the PutawayRule ruling): the row
    is read by the resolver, never referenced by other documents, so a human-readable
    number would be a second thing to keep meaningful.

    Scope is two-tier, mirroring every other most-specific-wins catalog in this app:
    an item-pinned row is the item's own truth ("this SKU ships in cases of 24"); a
    blank-item row is the tenant-wide default ("a case is twelve, generally"). Both may
    exist for the same pair — specificity decides which fires, never priority.

    ``(tenant, item, from_uom, to_uom)`` is unique. MariaDB's null-coalescing unique
    enforces that only when ``item`` is SET; two DEFAULT rows for one pair would both
    slip past the index, so :meth:`clean` re-probes duplicates explicitly (the
    ChannelListingMap ``external_variant_id`` precedent).
    """

    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, null=True, blank=True,
        related_name="uom_conversions",
        help_text="Exact-item rule (most specific); blank = tenant-wide default")
    from_uom = models.ForeignKey(
        "scm.UOM", on_delete=models.PROTECT, related_name="conversions_from",
        help_text="Unit being converted FROM (e.g. Case)")
    to_uom = models.ForeignKey(
        "scm.UOM", on_delete=models.PROTECT, related_name="conversions_to",
        help_text="Unit being converted INTO (e.g. Unit)")
    factor = models.DecimalField(
        max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="How many TO-units one FROM-unit holds — 12 means 1 Case = 12 Units")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["from_uom__code", "to_uom__code", "id"]
        unique_together = ("tenant", "item", "from_uom", "to_uom")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="inv_uom_tnt_active_idx"),
        ]

    def __str__(self):
        scope = f"{self.item.sku} · " if self.item_id else ""
        return f"{scope}{self.from_uom.code} → {self.to_uom.code} ×{self.factor}"

    # -- derived figures --------------------------------------------------------------------------

    @property
    def is_default(self):
        return self.item_id is None

    @property
    def reverse_factor(self):
        """How many FROM-units one TO-unit holds — the inverse reading of the same rule.

        Quantized, so a factor of 3 shows its exact 0.3333 inverse rather than a
        repeating decimal; converting back through the rounded inverse is lossy BY
        DESIGN and the calculator says so rather than pretending it is not.
        """
        try:
            return (Decimal("1") / self.factor).quantize(RESULT_QUANTUM)
        except (InvalidOperation, ZeroDivisionError):
            return None

    def convert(self, quantity):
        """Quantity expressed in the TO-unit under this single rule."""
        return (Decimal(quantity) * self.factor).quantize(RESULT_QUANTUM)

    # -- resolution -------------------------------------------------------------------------------

    @classmethod
    def resolve(cls, tenant, item, from_uom, to_uom):
        """The ONE direct rule for this pair, or None.

        Most-specific-wins: the item's own active row beats the tenant-wide active
        default; inactive rules never fire; nothing else ranks. Callers wanting
        multi-hop reachability want :func:`find_conversion_path`.
        """
        base = cls.objects.filter(
            tenant=tenant, is_active=True, from_uom=from_uom, to_uom=to_uom)
        if item is not None:
            hit = base.filter(item=item).first()
            if hit is not None:
                return hit
        return base.filter(item__isnull=True).first()

    # -- hygiene ----------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}
        if (self.from_uom_id and self.to_uom_id
                and self.from_uom_id == self.to_uom_id):
            errors["to_uom"] = "A conversion needs two different units."
        # Keyed off the FK ids, NOT truthiness of the object: an unset required FK must
        # surface as "required", never as a cross-tenant 500 (review C1 pattern).
        if self.item_id and self.item.tenant_id != self.tenant_id:
            errors["item"] = "That record belongs to another workspace."
        if self.from_uom_id and self.from_uom.tenant_id != self.tenant_id:
            errors["from_uom"] = "That record belongs to another workspace."
        if self.to_uom_id and self.to_uom.tenant_id != self.tenant_id:
            errors["to_uom"] = "That record belongs to another workspace."
        if errors:
            raise ValidationError(errors)
        # Explicit duplicate probe — the DB unique cannot see two item=NULL rows.
        if (self.tenant_id and self.from_uom_id and self.to_uom_id
                and type(self).objects.filter(
                    tenant_id=self.tenant_id,
                    item=self.item,
                    from_uom_id=self.from_uom_id,
                    to_uom_id=self.to_uom_id,
                ).exclude(pk=self.pk).exists()):
            raise ValidationError(
                "A conversion between these two units already exists for this scope.")


# -- the shared engine ----------------------------------------------------------------------------


def _active_edges(tenant, item):
    """Active rules as an adjacency map ``{from_pk: [(to_pk, rule), ...]}``.

    One flat query feeds the whole graph. For each directed pair the ITEM-pinned row
    overrides the tenant default (and among equals the lowest id wins), so the map
    holds exactly one rule per edge — a chain may still mix tiers across hops, because
    each edge resolves independently. Another SKU's private rule never enters this
    graph: when ``item`` names a SKU only its rows and the defaults qualify.
    """
    best = {}
    rows = (UomConversion.objects.filter(tenant=tenant, is_active=True)
            .select_related("from_uom", "to_uom", "item").order_by("id"))
    for rule in rows:
        if rule.item_id is not None and (item is None or rule.item_id != item.pk):
            continue
        key = (rule.from_uom_id, rule.to_uom_id)
        tier = 1 if rule.item_id is not None else 0
        prev = best.get(key)
        if prev is not None and prev[0] >= tier:
            continue
        best[key] = (tier, rule)
    edges = {}
    for (src, dst), (_tier, rule) in best.items():
        edges.setdefault(src, []).append((dst, rule))
    return edges


def find_conversion_path(tenant, item, from_uom, to_uom):
    """Shortest active rule chain joining the two units, or None.

    Breadth-first over :func:`_active_edges` with a depth cap — the returned list of
    rules reads in travel order (multiply each ``factor`` along it). An empty list
    means the pair is already the same unit; None means genuinely unreachable, and
    callers SAY so instead of guessing a rate.
    """
    if from_uom.pk == to_uom.pk:
        return []
    edges = _active_edges(tenant, item)
    visited = {from_uom.pk}
    queue = deque([(from_uom.pk, [])])
    while queue:
        node, path = queue.popleft()
        if len(path) >= MAX_PATH_DEPTH:
            continue
        for nxt, rule in edges.get(node, ()):
            if nxt == to_uom.pk:
                return path + [rule]
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [rule]))
    return None


def convert_quantity(tenant, item, quantity, from_uom, to_uom):
    """Convert ``quantity`` between units — ``(result | None, path | None)``.

    ``path is None`` means no route joined the units; the caller must treat that as
    "cannot convert", never as zero. Identity pairs convert trivially with an empty
    path. The product of the hop factors is quantized ONCE at the end, so intermediate
    precision survives multi-hop chains.
    """
    path = find_conversion_path(tenant, item, from_uom, to_uom)
    if path is None:
        return None, None
    amount = Decimal(quantity)
    for rule in path:
        amount *= rule.factor
    return amount.quantize(RESULT_QUANTUM), path
