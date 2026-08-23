"""Inventory 5.12 Multi-Location Management — LocationNetwork [LNW-].

The ORG-TIER tree, not the bin hierarchy. ``scm.Location`` already owns the physical
storage question (warehouse › zone › bin, with the append-only ``scm.StockMove``
ledger answering "how much sits there"); nothing anywhere records the organisational
question — how a holding rolls up through regions into distribution centres and
stores. That is what this ONE verb-less config table adds: ``LocationNetwork`` [LNW-],
a self-parenting tree whose nodes are curated short labels (``company`` / ``region``
/ ``dc`` / ``store``) and whose ``warehouse`` FK OPTIONALLY maps one node to one
stocked site. Deliberately a separate table from scm's hierarchy (L36): forking the
bin/zone spine to smuggle in org tiers would corrupt both meanings, while pointing
nodes AT the spine keeps global stock visibility derivable, never stored.

Rulings this file owns:

* **Leaf rule decided: warehouse attachable at ANY tier.** A stocking DC is a real
  shape — the DC node IS its warehouse. Leaf-only enforcement would need a
  children-walk on every save (an extra query plus a race window) for zero honesty
  gain; documented on the field help_text.
* **Cycle guards mirror scm's.** ``clean()`` refuses self-parentage and walks the
  chosen parent chain with a seen-set bounded at ``MAX_TREE_DEPTH`` hops (the
  ``Location.path()`` precedent at Locations.py:95), so a malformed or looping tree
  is a field error at save time and can never hang a page render later.
* **Zeros are real zeros** (orchestrator ruling): a node with no stock underneath
  aggregates to an honest 0 on the computed page — never None dressed as empty.
"""
from django.core.exceptions import ValidationError
from django.db import models

from apps.inventory.models._base import *  # noqa: F401,F403


#: Deepest ancestry any walk (validation guard, ``path()``, view roll-up) will follow.
#: Real org trees are shallow; the bound exists so a malformed self-parent row fails
#: fast instead of looping forever.
MAX_TREE_DEPTH = 8


class LocationNetwork(TenantNumbered):
    """One org-tier node [LNW-]: company › region › dc › store, optionally stocked.

    Pure configuration — no status machine, no quantities, no writes outside its own
    row. The whole value is derived: the tree gives the multi-location stock picture
    somewhere honest to roll up (see ``global_stock`` in the views layer).
    """

    NUMBER_PREFIX = "LNW"

    #: FROZEN from the 5.12 contract. Curated short tiers, not free-form types.
    NODE_TYPE_CHOICES = [
        ("company", "Company"),
        ("region", "Region"),
        ("dc", "Distribution Center"),
        ("store", "Store / Site"),
    ]

    #: Badge colour per tier, decided in ONE place. theme.css ships colour-named badge
    #: modifiers only — semantic variants do not exist and render unstyled (L33).
    NODE_CSS = {
        "company": "badge-slate",
        "region": "badge-info",
        "dc": "badge-amber",
        "store": "badge-green",
    }

    code = models.CharField(max_length=32)
    # Org-tier labels are curated short names — deliberately tighter than scm.Location.
    name = models.CharField(max_length=120)
    node_type = models.CharField(
        max_length=10, choices=NODE_TYPE_CHOICES, default="store")
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="children",
        help_text="Org-tier parent (blank = a top-level root of the network tree)")
    warehouse = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, null=True, blank=True,
        related_name="network_nodes",
        help_text=(
            "Stocked site this node maps to; blank = pure grouping. Attachable at "
            "ANY tier, not leaves only — a stocking DC node IS its warehouse "
            "(leaf-rule ruling). Warehouse-typed scm locations only: a bin is not "
            "a store."))
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        # Three constraints: number re-pins because TenantNumbered rows carry it
        # (FulfillmentWave precedent); NULL warehouses are excluded by SQL semantics,
        # so grouping nodes coexist freely under ("tenant", "warehouse").
        unique_together = (("tenant", "number"), ("tenant", "code"),
                           ("tenant", "warehouse"))
        indexes = [
            models.Index(fields=["tenant", "node_type"], name="inv_lnw_tnt_type_idx"),
        ]

    # -- presentation ---------------------------------------------------------------------------

    @property
    def node_css(self):
        """The badge class for this row's tier — see :attr:`NODE_CSS`."""
        return self.NODE_CSS.get(self.node_type, "badge-muted")

    def path(self):
        """Human-readable ancestry, e.g. 'HOLD-CO › REG-NORTH'. Bounded by a seen-set;
        guards a malformed self-parent cycle so a bad row can't hang the page
        (Location.path() precedent, Locations.py:95)."""
        parts, node, seen = [], self, set()
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            parts.append(node.code)
            node = node.parent
        return " › ".join(reversed(parts))

    # -- validation -----------------------------------------------------------------------------

    def clean(self):
        """Per-field cross-tenant rejection keyed where the user is looking, plus the
        structural guards: no self-parentage, warehouse-typed scm locations only, and
        a bounded seen-set walk refusing any parent chain that loops back through an
        ancestor. Runs for non-form writers too (admin, seeder) — the form's
        ``_reject_foreign`` narrows the selects, this is the authorization boundary."""
        super().clean()
        errors = {}
        if self.parent_id is not None:
            if self.parent_id == self.pk:
                errors["parent"] = "A node cannot be its own parent."
            elif self.parent.tenant_id != self.tenant_id:
                errors["parent"] = "That record belongs to another workspace."
            else:
                cycle = self._cycle_through_parent()
                if cycle:
                    errors["parent"] = (
                        "Setting this parent would create a loop in the network tree.")
        if self.warehouse_id is not None:
            if self.warehouse.tenant_id != self.tenant_id:
                errors["warehouse"] = "That record belongs to another workspace."
            elif self.warehouse.location_type != "warehouse":
                errors["warehouse"] = (
                    "Only warehouse-typed sites can attach here — a zone or bin is "
                    "not a store.")
        if errors:
            raise ValidationError(errors)

    def _cycle_through_parent(self):
        """True when the chosen parent's ancestry reaches back to ``self`` (or is
        itself already loopy/deeper than MAX_TREE_DEPTH). Same iterative seen-set
        walk as Location.path(), one depth cap stricter."""
        node, seen, hops = self.parent, set(), 0
        while node is not None:
            if node.pk == self.pk or node.pk in seen or hops >= MAX_TREE_DEPTH:
                return True
            seen.add(node.pk)
            node = node.parent
            hops += 1
        return False

    def __str__(self):
        return f"{self.code} · {self.name}"
