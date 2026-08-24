"""Inventory 5.12 — model invariants for LocationNetwork [LNW-].

One verb-less config table: the org-tier tree (company › region › dc › store) whose only
smarts are structural guards. Pinned here: per-tenant LNW numbering, the frozen tier
vocabulary + colour-named badges, clean()'s authorization boundary (self-parent, ancestor
loops, MAX_TREE_DEPTH chains, cross-tenant parent/warehouse, warehouse-typed sites only,
warehouse attachable at ANY tier), path() string assembly at each depth plus cycle safety
on an ORM-crafted loop, and all three unique_together constraints firing at the DB layer.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.inventory.models import LocationNetwork
from apps.inventory.models.MultiLocationManagement.LocationNetworks import MAX_TREE_DEPTH

pytestmark = pytest.mark.django_db


def _multiloc_node(tenant, code, **fields):
    """Plain ORM create — get_or_create-free so uniqueness tests hit real collisions."""
    return LocationNetwork.objects.create(tenant=tenant, code=code, **fields)


def _multiloc_site(tenant, code, **fields):
    """A scm.Location on the spine (defaults to warehouse-typed like every stocked site)."""
    from apps.scm.models import Location
    return Location.objects.create(
        tenant=tenant, code=code, name=f"Site {code}", location_type="warehouse", **fields)


# ------------------------------------------------------------------ basics / vocabulary


class TestMultilocBasics:
    def test_multiloc_str_is_code_dot_name(self, tenant_a):
        node = _multiloc_node(tenant_a, "NW-S", name="South Region")
        assert str(node) == "NW-S · South Region"

    def test_multiloc_number_sequence_per_tenant(self, tenant_a, tenant_b):
        first = _multiloc_node(tenant_a, "N1", name="first")
        second = _multiloc_node(tenant_a, "N2", name="second")
        assert first.number == "LNW-00001"
        assert second.number == "LNW-00002"
        # A second workspace's sequence starts at one — numbers never share across tenants.
        other = _multiloc_node(tenant_b, "N1", name="theirs")
        assert other.number == "LNW-00001"

    def test_multiloc_ordering_by_code(self, tenant_a):
        _multiloc_node(tenant_a, "NW-C", name="C last")
        _multiloc_node(tenant_a, "NW-A", name="A first")
        _multiloc_node(tenant_a, "NW-B", name="B middle")
        codes = list(LocationNetwork.objects.values_list("code", flat=True))
        assert codes == sorted(codes) == ["NW-A", "NW-B", "NW-C"]

    def test_multiloc_node_type_choices_frozen(self):
        assert LocationNetwork.NODE_TYPE_CHOICES == [
            ("company", "Company"),
            ("region", "Region"),
            ("dc", "Distribution Center"),
            ("store", "Store / Site"),
        ]
        # Meta sanity pinned alongside the vocabulary: the tier lookup index exists.
        assert "inv_lnw_tnt_type_idx" in {
            idx.name for idx in LocationNetwork._meta.indexes}

    def test_multiloc_node_css_complete_and_colour_named(self):
        # One entry per tier, all colour-named badge modifiers (theme.css ships no
        # semantic variants — L33).
        assert LocationNetwork.NODE_CSS == {
            "company": "badge-slate",
            "region": "badge-info",
            "dc": "badge-amber",
            "store": "badge-green",
        }
        for node_type, _label in LocationNetwork.NODE_TYPE_CHOICES:
            row = LocationNetwork(node_type=node_type)
            assert row.node_css == LocationNetwork.NODE_CSS[node_type]

    def test_multiloc_node_css_unknown_falls_back_to_muted(self):
        row = LocationNetwork(node_type="galaxy_office")
        assert row.node_css == "badge-muted"


# ------------------------------------------------------------------ clean(): tree guards


class TestMultilocCleanGuards:
    def test_multiloc_clean_refuses_self_parent(self, tenant_a):
        node = _multiloc_node(tenant_a, "SELF-1", name="Looping")
        node.parent = node
        with pytest.raises(ValidationError) as err:
            node.full_clean()
        assert "parent" in err.value.message_dict

    def test_multiloc_clean_refuses_ancestor_loop(self, tenant_a):
        """ORM-craft A(root) -> B, then point A back at B: the seen-set walk must refuse."""
        a = _multiloc_node(tenant_a, "LP-A", name="Root A")
        b = _multiloc_node(tenant_a, "LP-B", name="Child B", parent=a)
        a.parent = b
        with pytest.raises(ValidationError) as err:
            a.full_clean()
        assert "parent" in err.value.message_dict

    def test_multiloc_clean_refuses_chain_deeper_than_max_tree_depth(self, tenant_a):
        """A chain of MAX_TREE_DEPTH+1 nodes exists in the DB (save() runs no clean);
        hanging a 10th node under it is refused while the 9-deep boundary stays legal."""
        chain = [_multiloc_node(tenant_a, "CH-00", name="tier 0")]
        for i in range(1, MAX_TREE_DEPTH + 1):
            chain.append(_multiloc_node(
                tenant_a, f"CH-{i:02d}", name=f"tier {i}", parent=chain[-1]))
        assert len(chain) == MAX_TREE_DEPTH + 1
        too_deep = LocationNetwork(
            tenant=tenant_a, code="CH-DEEP", name="one past the cap", parent=chain[-1])
        with pytest.raises(ValidationError) as err:
            too_deep.full_clean()
        assert "parent" in err.value.message_dict
        boundary = LocationNetwork(
            tenant=tenant_a, code="CH-EDGE", name="at the cap", parent=chain[-2])
        boundary.full_clean()  # exactly MAX_TREE_DEPTH ancestors above -> allowed

    def test_multiloc_clean_rejects_foreign_parent_keyed_to_field(
            self, multiloc_company_a, multiloc_foreign_node_b):
        multiloc_company_a.parent = multiloc_foreign_node_b
        with pytest.raises(ValidationError) as err:
            multiloc_company_a.full_clean()
        assert err.value.message_dict["parent"] == [
            "That record belongs to another workspace."]

    def test_multiloc_clean_rejects_foreign_warehouse_keyed_to_field(
            self, tenant_a, multiloc_wh_b):
        node = _multiloc_node(tenant_a, "NW-FW", name="Foreign stock link")
        node.warehouse = multiloc_wh_b
        with pytest.raises(ValidationError) as err:
            node.full_clean()
        assert err.value.message_dict["warehouse"] == [
            "That record belongs to another workspace."]

    def test_multiloc_clean_refuses_non_warehouse_typed_site(self, tenant_a, multiloc_wh_a):
        from apps.scm.models import Location
        bin_row = Location.objects.create(
            tenant=tenant_a, code="MWH-A-B1", name="Bin under MWH-A",
            location_type="bin", parent=multiloc_wh_a)
        node = _multiloc_node(tenant_a, "NW-BIN", name="Points at a bin")
        node.warehouse = bin_row
        with pytest.raises(ValidationError) as err:
            node.full_clean()
        message = err.value.message_dict["warehouse"][0]
        assert "warehouse-typed" in message

    def test_multiloc_warehouse_attachable_at_any_tier(
            self, multiloc_dc_a, multiloc_store_a, tenant_a):
        """The leaf-rule ruling: a stocking DC node IS its warehouse — the fixture proves a
        tier-3 attachment validates, and a store-tier attachment validates just as well."""
        multiloc_dc_a.full_clean()  # company › region › dc(warehouse) — no error raised

        multiloc_store_a.warehouse = _multiloc_site(tenant_a, "MSTORE-A")
        multiloc_store_a.full_clean()  # leaf tier equally legal — deliberately unenforced


# ------------------------------------------------------------------ path()


class TestMultilocPath:
    def test_multiloc_path_root_returns_own_code(self, multiloc_company_a):
        assert multiloc_company_a.path() == "NW-CO-A"

    def test_multiloc_path_depth_two_and_three_join_with_separator(
            self, multiloc_region_a, multiloc_dc_a):
        assert multiloc_region_a.path() == "NW-CO-A › NW-RG-A"
        # The contract label shape: "CO › REG › DC" — root leftmost, self rightmost.
        assert multiloc_dc_a.path() == "NW-CO-A › NW-RG-A › NW-DC-A"

    def test_multiloc_path_cycle_safe_on_orm_crafted_loop(self, tenant_a):
        """update() bypasses clean(), so a looping tree CAN exist in raw data; path()'s
        bounded seen-set walk must terminate and never hang a page render."""
        a = _multiloc_node(tenant_a, "CY-A", name="Cycle A")
        b = _multiloc_node(tenant_a, "CY-B", name="Cycle B", parent=a)
        LocationNetwork.objects.filter(pk=a.pk).update(parent=b)
        a.refresh_from_db()
        parts = a.path().split(" › ")
        assert set(parts) == {"CY-A", "CY-B"}  # terminated after one lap, both codes once


# ------------------------------------------------------------------ uniqueness


class TestMultilocUniqueness:
    def test_multiloc_duplicate_code_raises_integrity_error(self, tenant_a):
        _multiloc_node(tenant_a, "NW-DUP", name="Original")
        with pytest.raises(IntegrityError):
            _multiloc_node(tenant_a, "NW-DUP", name="Impostor")

    def test_multiloc_same_warehouse_twice_raises_integrity_error(
            self, tenant_a, multiloc_dc_a, multiloc_wh_a):
        """The dc fixture already maps NW-DC-A -> MWH-A; a second mapping of the same
        stocked site collides on (tenant, warehouse)."""
        with pytest.raises(IntegrityError):
            _multiloc_node(
                tenant_a, "NW-DC-TWIN", name="Second map of MWH-A", warehouse=multiloc_wh_a)

    def test_multiloc_duplicate_number_raises_integrity_error(self, tenant_a):
        original = _multiloc_node(tenant_a, "NW-NUM", name="Numbered first")
        with pytest.raises(IntegrityError):
            _multiloc_node(
                tenant_a, "NW-OTHER", name="Steals a number", number=original.number)


# ------------------------------------------------------------------ relations & honesty


class TestMultilocRelationsAndHonesty:
    def test_multiloc_children_reverse_related(self, multiloc_region_a, multiloc_dc_a,
                                               multiloc_store_a, multiloc_company_a):
        kids = list(multiloc_region_a.children.all())
        assert kids == [multiloc_dc_a, multiloc_store_a]  # Meta.ordering by code
        assert multiloc_dc_a.parent_id == multiloc_region_a.pk

    def test_multiloc_network_nodes_reverse_from_scm_location(
            self, multiloc_dc_a, multiloc_wh_a, multiloc_wh_b):
        assert multiloc_dc_a in list(multiloc_wh_a.network_nodes.all())
        assert multiloc_wh_a.network_nodes.count() == 1  # unique_together guarantees it
        assert not multiloc_wh_b.network_nodes.exists()  # foreign site untouched

    def test_multiloc_is_active_toggle_is_harmless(self, multiloc_store_a):
        """Verb-less config honesty: no status machine gates edits here (no wave-style
        ``is_editable`` property exists), and toggling activity changes nothing else."""
        assert not hasattr(multiloc_store_a, "is_editable")
        number_before = multiloc_store_a.number
        multiloc_store_a.is_active = False
        multiloc_store_a.full_clean()
        multiloc_store_a.save()
        multiloc_store_a.refresh_from_db()
        assert multiloc_store_a.is_active is False
        assert multiloc_store_a.number == number_before  # numbering never re-pins
        multiloc_store_a.is_active = True
        multiloc_store_a.save(update_fields=["is_active"])
        multiloc_store_a.refresh_from_db()
        assert multiloc_store_a.is_active is True
