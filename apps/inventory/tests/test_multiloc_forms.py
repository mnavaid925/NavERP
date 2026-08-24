"""Inventory 5.12 — form boundary.

The network tree is plain configuration, so its boundary mirrors the putaway-rule lane:
Meta carries EXACTLY the seven contract fields (``number`` stays off — minted by
TenantNumbered save()), ``clean_code`` strips at FIELD level so the ("tenant","code")
unique check judges the stored value, and placement (parent/warehouse) is policed twice —
``_reject_foreign`` keys field errors while the model's own ``clean()`` adds the structural
guards (self-parentage, cycles), which only fire because ``TenantUniqueMixin`` stamps
``instance.tenant`` during CREATE validation. These tests drive ``LocationNetworkForm``
directly, no client.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.inventory.forms import LocationNetworkForm
from apps.inventory.models import LocationNetwork

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _multiloc_site(tenant, code):
    """An UNUSED warehouse-typed ``scm.Location`` — the (tenant, code) spine makes this
    get_or_create-safe. Fresh sites matter here: ("tenant","warehouse") is UNIQUE among
    nodes, so the conftest's MWH-A is already taken by multiloc_dc_a."""
    from apps.scm.models import Location
    site, _created = Location.objects.get_or_create(
        tenant=tenant, code=code,
        defaults={"name": f"Site {code}", "location_type": "warehouse"})
    return site


def _multiloc_payload(**overrides):
    """A create-shaped payload. Both placement FKs blank = root grouping node, the
    minimal legal shape; callers override them for attached-node vectors."""
    data = {
        "code": "NW-NW-01",
        "name": "Northwest Node",
        "node_type": "store",
        "parent": "",
        "warehouse": "",
        "is_active": "on",
        "notes": "Org-tier node for the multi-location lane.",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ LocationNetworkForm


class TestLocationNetworkForm:
    def test_multiloc_meta_fields_are_exactly_the_seven_contract_fields_in_order(self, tenant_a):
        form = LocationNetworkForm(tenant=tenant_a)
        assert list(LocationNetworkForm.Meta.fields) == [
            "code", "name", "node_type", "parent", "warehouse",
            "is_active", "notes",
        ]
        # number is minted by TenantNumbered.save(); tenant is stamped by the mixin —
        # neither may ever be mass-assigned through a crafted POST.
        assert "number" not in form.fields
        assert "tenant" not in form.fields

    def test_multiloc_unbound_form_prerenders_model_defaults_as_initial(self, tenant_a):
        """The add page must show a ticked active checkbox before the user types anything
        (Django 5.1 surfaces model defaults as FORM-FIELD initial)."""
        form = LocationNetworkForm(tenant=tenant_a)
        assert not form.is_bound
        assert form["is_active"].initial is True

    def test_multiloc_full_payload_saves_with_company_parent_and_warehouse(
            self, tenant_a, multiloc_company_a, multiloc_wh_a):
        site = _multiloc_site(tenant_a, "MWH-A2")  # MWH-A itself is taken by the DC node
        form = LocationNetworkForm(
            data=_multiloc_payload(code="NW-DC-X", name="Annex DC", node_type="dc",
                                   parent=multiloc_company_a.pk, warehouse=site.pk),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.parent_id == multiloc_company_a.pk
        assert obj.warehouse_id == site.pk
        assert obj.number.startswith("LNW-")
        assert obj.is_active is True

    def test_multiloc_bare_store_leaf_without_warehouse_saves(self, tenant_a):
        """Blank parent AND blank warehouse is a top-level pure-grouping store — the
        minimal legal shape must save, not reject."""
        before = LocationNetwork.objects.count()
        form = LocationNetworkForm(
            data=_multiloc_payload(code="NW-ST-BARE", name="Bare Leaf"), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.node_type == "store"
        assert obj.parent_id is None
        assert obj.warehouse_id is None
        assert LocationNetwork.objects.count() == before + 1

    def test_multiloc_code_surrounding_whitespace_stripped_before_save(self, tenant_a):
        """clean_code trims at FIELD level, so what lands in the DB is the trimmed value —
        and the ("tenant","code") unique check judged that same value."""
        form = LocationNetworkForm(
            data=_multiloc_payload(code="  PAD-01  "), tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.save().code == "PAD-01"

    def test_multiloc_whitespace_only_code_is_field_error_not_a_crash(self, tenant_a):
        """CharField.strip flattens "   " to "" before clean_code runs, so this surfaces
        as Django's own required message — either rejection text is fine, the outcome
        (invalid, code-keyed field error, nothing written) is the contract."""
        before = LocationNetwork.objects.count()
        form = LocationNetworkForm(data=_multiloc_payload(code="   "), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["code"]
        joined = " ".join(form.errors["code"]).lower()
        assert "required" in joined or "blank" in joined or "whitespace" in joined
        assert LocationNetwork.objects.count() == before

    def test_multiloc_empty_code_is_required_error_not_a_crash(self, tenant_a):
        form = LocationNetworkForm(data=_multiloc_payload(code=""), tenant=tenant_a)
        assert not form.is_valid()
        assert "code" in form.errors
        assert "required" in " ".join(form.errors["code"]).lower()

    def test_multiloc_cross_tenant_parent_pk_is_field_error_and_creates_nothing(
            self, tenant_a, multiloc_foreign_node_b):
        before = LocationNetwork.objects.count()
        form = LocationNetworkForm(
            data=_multiloc_payload(parent=multiloc_foreign_node_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["parent"]
        assert LocationNetwork.objects.count() == before

    def test_multiloc_cross_tenant_warehouse_pk_is_field_error_and_creates_nothing(
            self, tenant_a, multiloc_wh_b):
        before = LocationNetwork.objects.count()
        form = LocationNetworkForm(
            data=_multiloc_payload(warehouse=multiloc_wh_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["warehouse"]
        assert LocationNetwork.objects.count() == before

    def test_multiloc_duplicate_code_post_is_validation_error_not_a_crash(
            self, tenant_a, multiloc_company_a):
        """C1 regression: ("tenant","code") never form-validates without the mixin — the
        crafted duplicate must come back as an "__all__" error, never an IntegrityError."""
        before = LocationNetwork.objects.count()
        form = LocationNetworkForm(
            data=_multiloc_payload(code=multiloc_company_a.code, name="Impostor Co"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "__all__" in form.errors  # unique_together reports on non-field errors
        assert LocationNetwork.objects.count() == before

    def test_multiloc_second_node_on_same_warehouse_is_warehouse_error(
            self, tenant_a, multiloc_dc_a, multiloc_wh_a):
        """C-contract regression: ONE node per stocked site. multiloc_dc_a already owns
        MWH-A, so a second node pointing there must fail validation — again on "__all__",
        naming warehouse — with zero rows written."""
        before = LocationNetwork.objects.count()
        form = LocationNetworkForm(
            data=_multiloc_payload(code="NW-DUP-WH", name="Warehouse Squatter",
                                   warehouse=multiloc_wh_a.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "__all__" in form.errors
        assert any("warehouse" in msg.lower() for msg in form.errors["__all__"])
        assert LocationNetwork.objects.count() == before

    def test_multiloc_self_parent_via_edit_form_is_parent_error(
            self, tenant_a, multiloc_company_a):
        """Editing a node with ITSELF as parent passes choice-validation (it IS a
        same-tenant node) and must die in the model's self-parentage guard as a plain
        parent field error — never a recursion crash or a silent save."""
        form = LocationNetworkForm(
            data=_multiloc_payload(code=multiloc_company_a.code,
                                   name=multiloc_company_a.name,
                                   node_type="company",
                                   parent=multiloc_company_a.pk),
            instance=multiloc_company_a, tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["parent"]
        assert any("own parent" in msg.lower() for msg in form.errors["parent"])

    def test_multiloc_parent_own_descendant_cycle_rejected_via_model_clean(
            self, tenant_a, multiloc_company_a, multiloc_store_a):
        """A direct cycle can't be typed into the form (the parent <select> offers any
        same-tenant node), so the reachable vector is parent = own DESCENDANT: making the
        company hang under its store loops the tree, and the bounded seen-set walk in
        clean() refuses it consistently through full_clean."""
        form = LocationNetworkForm(
            data=_multiloc_payload(code=multiloc_company_a.code,
                                   name=multiloc_company_a.name,
                                   node_type="company",
                                   parent=multiloc_store_a.pk),
            instance=multiloc_company_a, tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["parent"]
        assert any("loop" in msg.lower() for msg in form.errors["parent"])
        multiloc_company_a.refresh_from_db()
        assert multiloc_company_a.parent_id is None

    def test_multiloc_tenant_kwarg_stamps_instance_before_model_clean_sec1(
            self, tenant_a, multiloc_company_a, multiloc_wh_b):
        """SEC-1 two-jobs rule: the mixin stamps ``instance.tenant`` during construction,
        BEFORE ``is_valid()``, so the model's cross-tenant ``clean()`` compares the chosen
        FKs against the real workspace instead of None. The bare-instance contrast shows
        the false rejection the stamp prevents."""
        form = LocationNetworkForm(
            data=_multiloc_payload(parent=multiloc_company_a.pk),
            tenant=tenant_a)
        assert form.instance.tenant_id == tenant_a.pk  # stamped pre-validation
        assert form.is_valid(), form.errors
        assert form.save().tenant_id == tenant_a.pk

        bare = LocationNetwork(parent=multiloc_company_a, warehouse=multiloc_wh_b)
        assert bare.tenant_id is None
        with pytest.raises(ValidationError) as excinfo:
            bare.full_clean()
        assert {"parent", "warehouse"} <= set(excinfo.value.error_dict)

    def test_multiloc_edit_with_unchanged_data_revalidates_clean(
            self, tenant_a, multiloc_dc_a):
        """Re-submitting a node's own values must pass — no false cross-tenant or
        uniqueness rejection on the edit path, and saving must not mint a second row."""
        before = LocationNetwork.objects.count()
        form = LocationNetworkForm(
            data=_multiloc_payload(
                code=multiloc_dc_a.code, name=multiloc_dc_a.name,
                node_type=multiloc_dc_a.node_type, parent=multiloc_dc_a.parent_id,
                warehouse=multiloc_dc_a.warehouse_id, notes=multiloc_dc_a.notes),
            instance=multiloc_dc_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.pk == multiloc_dc_a.pk
        assert LocationNetwork.objects.count() == before
