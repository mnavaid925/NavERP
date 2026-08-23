"""Inventory 5.4 — form boundary.

The putaway rule is plain configuration, so its boundary is narrower than the document
forms: Meta carries EXACTLY the seven contract fields, the model's own ``clean()`` does the
cross-tenant and same-location policing (which only fires because ``TenantUniqueMixin``
stamps ``instance.tenant`` during CREATE validation — the SEC-1 two-jobs rule), and
``_reject_foreign`` re-checks every chosen FK where it renders as a field error. These tests
drive ``PutawayRuleForm`` directly, no client.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.inventory.forms import PutawayRuleForm
from apps.inventory.models import PutawayRule
from apps.scm.models import ItemCategory

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _receiving_category(tenant, name):
    """A minimal ``scm.ItemCategory`` row — the conftest ships no category fixtures."""
    return ItemCategory.objects.create(tenant=tenant, name=name)


def _receiving_payload(**overrides):
    """A valid same-tenant create payload. ``destination`` is the model's ONE required FK,
    so callers override it (the blank here is exactly the missing-required vector)."""
    data = {
        "item": "",
        "category": "",
        "source_location": "",
        "destination": "",
        "priority": "100",
        "is_active": "on",
        "notes": "Standing putaway instruction for the receiving lane.",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ PutawayRuleForm


class TestPutawayRuleForm:
    def test_receiving_meta_fields_are_exactly_the_seven_contract_fields_in_order(self):
        assert list(PutawayRuleForm.Meta.fields) == [
            "item", "category", "source_location", "destination",
            "priority", "is_active", "notes",
        ]

    def test_receiving_unbound_form_prerenders_model_defaults_as_initial(self, tenant_a):
        """Django 5.1 surfaces model defaults as FORM-FIELD initial: the add page must show
        priority 100 and a ticked active checkbox before the user types anything."""
        form = PutawayRuleForm(tenant=tenant_a)
        assert not form.is_bound
        assert form["priority"].initial == 100
        assert form["is_active"].initial is True

    def test_receiving_valid_item_scoped_rule_saves(self, tenant_a, item_a,
                                                    receiving_loc_dock_a,
                                                    receiving_loc_bin_a):
        form = PutawayRuleForm(
            data=_receiving_payload(item=item_a.pk, source_location=receiving_loc_dock_a.pk,
                                    destination=receiving_loc_bin_a.pk),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.item_id == item_a.pk
        assert obj.source_location_id == receiving_loc_dock_a.pk
        assert obj.destination_id == receiving_loc_bin_a.pk
        assert obj.priority == 100
        assert obj.is_active is True

    def test_receiving_fully_blank_catch_all_is_legal(self, tenant_a, receiving_loc_bin_a):
        """No item AND no category is the tier-1 catch-all — overlapping rules are legal by
        design, so this must save, not reject."""
        before = PutawayRule.objects.count()
        form = PutawayRuleForm(
            data=_receiving_payload(destination=receiving_loc_bin_a.pk), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.item_id is None
        assert obj.category_id is None
        assert PutawayRule.objects.count() == before + 1

    def test_receiving_category_only_rule_saves(self, tenant_a, receiving_loc_bin_a):
        category = _receiving_category(tenant_a, "Cold Chain")
        form = PutawayRuleForm(
            data=_receiving_payload(category=category.pk,
                                    destination=receiving_loc_bin_a.pk),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.category_id == category.pk
        assert obj.item_id is None

    def test_receiving_foreign_item_pk_is_field_error_and_creates_nothing(
            self, tenant_a, item_b, receiving_loc_bin_a):
        before = PutawayRule.objects.count()
        form = PutawayRuleForm(
            data=_receiving_payload(destination=receiving_loc_bin_a.pk, item=item_b.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["item"]
        assert PutawayRule.objects.count() == before

    def test_receiving_foreign_category_pk_is_field_error_and_creates_nothing(
            self, tenant_a, tenant_b, receiving_loc_bin_a):
        foreign_category = _receiving_category(tenant_b, "Globex Cold Chain")
        before = PutawayRule.objects.count()
        form = PutawayRuleForm(
            data=_receiving_payload(destination=receiving_loc_bin_a.pk,
                                    category=foreign_category.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["category"]
        assert PutawayRule.objects.count() == before

    def test_receiving_foreign_source_location_pk_is_field_error_and_creates_nothing(
            self, tenant_a, receiving_loc_dock_b, receiving_loc_bin_a):
        before = PutawayRule.objects.count()
        form = PutawayRuleForm(
            data=_receiving_payload(source_location=receiving_loc_dock_b.pk,
                                    destination=receiving_loc_bin_a.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["source_location"]
        assert PutawayRule.objects.count() == before

    def test_receiving_foreign_destination_pk_is_field_error_and_creates_nothing(
            self, tenant_a, receiving_loc_bin_b):
        before = PutawayRule.objects.count()
        form = PutawayRuleForm(
            data=_receiving_payload(destination=receiving_loc_bin_b.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["destination"]
        assert PutawayRule.objects.count() == before

    def test_receiving_same_source_and_destination_gives_non_field_error(
            self, tenant_a, receiving_loc_dock_a):
        before = PutawayRule.objects.count()
        form = PutawayRuleForm(
            data=_receiving_payload(source_location=receiving_loc_dock_a.pk,
                                    destination=receiving_loc_dock_a.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        non_field = form.non_field_errors()
        assert non_field
        assert "different" in " ".join(non_field).lower()
        assert PutawayRule.objects.count() == before

    def test_receiving_missing_destination_is_required_error_not_a_crash(
            self, tenant_a, item_a, receiving_loc_dock_a):
        """C1 regression at FORM level: an omitted destination must come back as a plain
        "required" field error — never escape full_clean as RelatedObjectDoesNotExist."""
        form = PutawayRuleForm(
            data=_receiving_payload(item=item_a.pk, source_location=receiving_loc_dock_a.pk),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "destination" in form.errors
        assert "required" in " ".join(form.errors["destination"]).lower()

    def test_receiving_tenant_kwarg_stamps_instance_before_model_clean_sec1(
            self, tenant_a, item_a, receiving_loc_dock_a, receiving_loc_bin_a):
        """SEC-1 two-jobs rule: the mixin stamps ``instance.tenant`` during construction,
        BEFORE ``is_valid()``, so the model's cross-tenant ``clean()`` compares the chosen
        FKs against the real workspace instead of None. The bare-instance contrast shows the
        false rejection the stamp prevents: with ``tenant_id`` still unset, the identical
        all-same-tenant rule is flagged on every FK."""
        form = PutawayRuleForm(
            data=_receiving_payload(item=item_a.pk, source_location=receiving_loc_dock_a.pk,
                                    destination=receiving_loc_bin_a.pk),
            tenant=tenant_a)
        assert form.instance.tenant_id == tenant_a.pk  # stamped pre-validation
        assert form.is_valid(), form.errors
        assert form.save().tenant_id == tenant_a.pk

        bare = PutawayRule(item=item_a, destination=receiving_loc_bin_a)
        assert bare.tenant_id is None
        with pytest.raises(ValidationError) as excinfo:
            bare.full_clean()
        assert {"item", "destination"} <= set(excinfo.value.error_dict)

    def test_receiving_edit_with_unchanged_data_validates_clean(
            self, tenant_a, receiving_rule_a):
        """Re-submitting a rule's own values must pass — no false cross-tenant rejection on
        the edit path, and saving must not mint a second row."""
        before = PutawayRule.objects.count()
        form = PutawayRuleForm(
            data=_receiving_payload(
                item=receiving_rule_a.item_id,
                source_location=receiving_rule_a.source_location_id,
                destination=receiving_rule_a.destination_id,
                priority=str(receiving_rule_a.priority),
                notes=receiving_rule_a.notes),
            instance=receiving_rule_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.pk == receiving_rule_a.pk
        assert PutawayRule.objects.count() == before

    def test_receiving_notes_optional_and_priority_accepts_integer_string(
            self, tenant_a, receiving_loc_bin_a):
        form = PutawayRuleForm(
            data=_receiving_payload(destination=receiving_loc_bin_a.pk,
                                    notes="", priority="55"),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.notes == ""
        assert obj.priority == 55

    def test_receiving_script_notes_saved_raw_escaping_is_template_side(
            self, tenant_a, receiving_loc_bin_a):
        """The form is not a sanitizer: markup passes through verbatim and escaping is the
        template layer's job at render time — mangling stored text here would only corrupt
        legitimate notes."""
        raw = "<script>alert('x')</script>"
        form = PutawayRuleForm(
            data=_receiving_payload(destination=receiving_loc_bin_a.pk, notes=raw),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.save().notes == raw

    def test_receiving_junk_priority_is_field_error_not_a_crash(
            self, tenant_a, receiving_loc_bin_a):
        before = PutawayRule.objects.count()
        form = PutawayRuleForm(
            data=_receiving_payload(destination=receiving_loc_bin_a.pk, priority="abc"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["priority"]
        assert PutawayRule.objects.count() == before

    def test_receiving_crafted_post_cannot_mass_assign_tenant(
            self, tenant_a, tenant_b, receiving_loc_bin_a):
        """``tenant`` is not a form field: smuggling it in POST data changes nothing — the
        mixin stamps the real workspace and save() lands on tenant_a."""
        form = PutawayRuleForm(
            data=_receiving_payload(destination=receiving_loc_bin_a.pk,
                                    tenant=tenant_b.pk),
            tenant=tenant_a)
        assert "tenant" not in form.fields
        assert form.is_valid(), form.errors
        assert form.save().tenant_id == tenant_a.pk
