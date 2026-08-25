"""Inventory 5.15 Quality Control (QC) & Inspection — form boundary.

Same discipline as the 5.5 file, over QC's own documents: tenant-scoped dropdowns refuse a
foreign pk at choice-validation, ``_reject_foreign`` stands beneath it (so a narrowed
``<select>`` stays UX, never the authorization boundary), workspace identity is never a form
field, and lifecycle columns (status / resolution stamps) move solely through the verbs.

* ``QcChecklistForm`` + ``QcChecklistItemFormSet`` — parent and inline checkpoints; untouched
  extra rows are ignored (empty ``cleaned_data``), a half-touched extra row fails loudly, and
  the DELETE checkbox removes an existing checkpoint.
* ``DefectReportForm`` — evidence photos are images-only below the core 20 MB ceiling; the
  external-link pointer stands alone when there is no file.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.inventory.forms import (
    DefectReportForm,
    QcChecklistForm,
    QcChecklistItemFormSet,
    QcRoutingRuleForm,
    QuarantineOrderForm,
)
from apps.inventory.models import (
    DefectReport,
    QcChecklist,
    QcChecklistItem,
    QcRoutingRule,
    QuarantineOrder,
)
from apps.scm.models import ItemCategory, LotSerial, NonConformance

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _checklist_data(**overrides):
    # Values are STRINGS, as a real QueryDict POST would carry them.
    data = {
        "name": "Dock intake check",
        "item": "",
        "vendor": "",
        "description": "",
        "is_active": "on",
    }
    data.update(overrides)
    return data


def _checkpoint_row(label="", kind="visual", expected_result="", sequence="10", **extra):
    """One rendered checkpoint row's POST keys, as a browser sends them: the hidden id key and
    the model-default-initialised controls (kind / is_mandatory / sequence render pre-filled),
    so an UNTOUCHED extra row posts only defaults back — 'id'/'DELETE' ride in via extra."""
    row = {
        "label": label,
        "kind": kind,
        "expected_result": expected_result,
        "sequence": sequence,
        "id": "",
        "is_mandatory": "on",
    }
    row.update(extra)
    return row


def _items_post(prefix, rows):
    """A management-form-complete POST dict for QcChecklistItemFormSet, bound under its REAL
    default prefix; id-bearing rows (the initial ones) must come first."""
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(rows)),
        f"{prefix}-INITIAL_FORMS": str(sum(1 for r in rows if r.get("id"))),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for i, row in enumerate(rows):
        for name, value in row.items():
            data[f"{prefix}-{i}-{name}"] = value
    return data


def _rule_data(**overrides):
    data = {
        "name": "Inspect inbound electronics",
        "item": "",
        "category": "",
        "vendor": "",
        "verdict": "inspect",
        "qc_location": "",
        "priority": "10",
        "is_active": "on",
        "notes": "",
    }
    data.update(overrides)
    return data


def _qrd_data(item, source, zone, **overrides):
    data = {
        "item": str(item.pk),
        "lot_serial": "",
        "source_location": str(source.pk),
        "quarantine_location": str(zone.pk),
        "quantity": "3",
        "reason": "qc_hold",
        "reference": "GRN-00012",
        "notes": "",
    }
    data.update(overrides)
    return data


def _defect_data(**overrides):
    data = {
        "item": "",
        "location": "",
        "lot_serial": "",
        "quantity": "1",
        "defect_type": "packaging",
        "severity": "major",
        "discovered_during": "receiving",
        "description": "Crushed carton corner",
        "photo_url": "",
        "reported_by": "",
        "ncr": "",
    }
    data.update(overrides)
    return data


def _assert_foreign_rejected(form, field):
    """The crafted POST dies ON the named field: the scoped dropdown words it 'Select a valid
    choice' and _reject_foreign/model clean beneath word it 'another workspace' — either
    wording is a rejection (same ruling as test_catalog_forms.py)."""
    assert not form.is_valid()
    assert form.errors[field]
    joined = " ".join(form.errors[field]).lower()
    assert "workspace" in joined or "choice" in joined


# ------------------------------------------------------------------ QcChecklistForm + items


class TestQcChecklistForms:
    def test_valid_save_saves_parent_and_only_the_touched_rows(
            self, tenant_a, item_a):
        """crud_create flow: parent form then the inline formset; two UNTOUCHED extra rows
        arrive as blank keys and are ignored — exactly one checkpoint row lands, no orphans."""
        form = QcChecklistForm(data=_checklist_data(item=str(item_a.pk)), tenant=tenant_a)
        assert form.is_valid(), form.errors
        checklist = form.save(commit=False)
        checklist.tenant = tenant_a
        checklist.save()

        prefix = QcChecklistItemFormSet().prefix
        rows = [
            _checkpoint_row("Carton seal intact"),
            _checkpoint_row(),  # untouched extra row
            _checkpoint_row(),  # untouched extra row
        ]
        formset = QcChecklistItemFormSet(data=_items_post(prefix, rows), instance=checklist)
        assert formset.is_valid(), formset.errors

        # The qcchecklist_create loop, verbatim: blank extras carry EMPTY cleaned_data.
        for item_form in formset:
            if not item_form.cleaned_data or item_form.cleaned_data.get("DELETE"):
                continue
            row = item_form.save(commit=False)
            row.tenant = tenant_a
            row.checklist = checklist
            row.save()

        assert [r.label for r in checklist.checklist_items.all()] == ["Carton seal intact"]
        assert QcChecklistItem.objects.count() == 1  # no orphan checkpoint rows anywhere

    def test_delete_checkbox_removes_an_existing_checkpoint_row(
            self, tenant_a, qc_checklist_a):
        """Edit flow over the seeded two-row checklist: ticking DELETE on the first row drops
        that very row from the DB and leaves its sibling untouched."""
        existing = list(qc_checklist_a.checklist_items.order_by("sequence"))
        prefix = QcChecklistItemFormSet().prefix
        rows = [
            _checkpoint_row(existing[0].label, id=str(existing[0].pk), DELETE="on"),
            _checkpoint_row(existing[1].label, sequence="20", id=str(existing[1].pk)),
            _checkpoint_row(),  # untouched extra row
        ]
        formset = QcChecklistItemFormSet(
            data=_items_post(prefix, rows), instance=qc_checklist_a)
        assert formset.is_valid(), formset.errors

        # The qcchecklist_edit loop, verbatim.
        for item_form in formset:
            if not item_form.cleaned_data:
                continue
            if item_form.cleaned_data.get("DELETE"):
                if item_form.instance.pk:
                    item_form.instance.delete()
                continue
            row = item_form.save(commit=False)
            row.tenant = qc_checklist_a.tenant
            row.checklist = qc_checklist_a
            row.save()

        assert not QcChecklistItem.objects.filter(pk=existing[0].pk).exists()
        assert qc_checklist_a.checklist_items.count() == 1
        assert qc_checklist_a.checklist_items.get().pk == existing[1].pk

    def test_half_touched_extra_row_makes_formset_invalid(self, tenant_a):
        """An extra row that grew a kind of its own (off the rendered default) while keeping a
        blank label is NOT ignorable — the formset refuses it on the label field instead of
        silently minting an unnamed checkpoint."""
        rows = [
            _checkpoint_row("Seal intact"),
            _checkpoint_row(kind="quantity"),  # half-touched: kind re-picked, label blank
        ]
        formset = QcChecklistItemFormSet(
            data=_items_post(QcChecklistItemFormSet().prefix, rows),
            instance=QcChecklist(tenant=tenant_a))  # unsaved instance, like the create view
        assert not formset.is_valid()
        assert "label" in formset.errors[1]
        assert QcChecklistItem.objects.count() == 0

    @pytest.mark.parametrize("field", ["item", "vendor"])
    def test_crafted_post_foreign_fk_is_field_error(
            self, tenant_a, item_b, vendor_party_b, field):
        foreign = {"item": str(item_b.pk), "vendor": str(vendor_party_b.pk)}
        before = QcChecklist.objects.count()
        form = QcChecklistForm(
            data=_checklist_data(**{field: foreign[field]}), tenant=tenant_a)
        _assert_foreign_rejected(form, field)
        assert QcChecklist.objects.count() == before


# ------------------------------------------------------------------ QcRoutingRuleForm


class TestQcRoutingRuleForm:
    @pytest.mark.parametrize("field", ["item", "category", "qc_location"])
    def test_crafted_post_foreign_fk_is_field_error(
            self, tenant_a, tenant_b, item_a, item_b, qc_zone_a, qc_zone_b, field):
        """Each routing vector accepts only this workspace's rows — a foreign pk posted past
        the narrowed <select> is refused on that field, and no rule row is written."""
        category_b = ItemCategory.objects.create(tenant=tenant_b, name="Globex widgets")
        foreign = {
            "item": str(item_b.pk),
            "category": str(category_b.pk),
            "qc_location": str(qc_zone_b.pk),
        }
        data = _rule_data(item=str(item_a.pk), qc_location=str(qc_zone_a.pk))
        data.update({field: foreign[field]})
        before = QcRoutingRule.objects.count()
        form = QcRoutingRuleForm(data=data, tenant=tenant_a)
        _assert_foreign_rejected(form, field)
        assert QcRoutingRule.objects.count() == before


# ------------------------------------------------------------------ QuarantineOrderForm


class TestQuarantineOrderForm:
    def test_status_and_resolved_columns_are_not_form_fields(self):
        """Exactly eight fields: the hold lifecycle (draft→quarantined→…) and its stamps live
        in the verbs, so none can be mass-assigned through a crafted POST."""
        assert set(QuarantineOrderForm._meta.fields) == {
            "item", "lot_serial", "source_location", "quarantine_location",
            "quantity", "reason", "reference", "notes"}
        for name in ("status", "resolved_at", "quarantined_at"):
            assert name not in QuarantineOrderForm.base_fields

    def test_missing_required_fields_invalid_and_nothing_saved(self, tenant_a):
        form = QuarantineOrderForm(data={}, tenant=tenant_a)
        assert not form.is_valid()
        for name in ("item", "source_location", "quarantine_location", "quantity"):
            assert name in form.errors
        assert QuarantineOrder.objects.count() == 0

    @pytest.mark.parametrize("field", ["item", "lot_serial", "source_location",
                                       "quarantine_location"])
    def test_crafted_post_foreign_fk_is_field_error(
            self, tenant_a, tenant_b, item_a, item_b, qc_warehouse_a, qc_zone_a, qc_zone_b,
            field):
        """All four tenant-scoped FK vectors are guarded: a Globex pk smuggled into any of
        them is a field error and no segregation order is drafted."""
        foreign_lot = LotSerial.objects.create(tenant=tenant_b, item=item_b, number="GLO-LOT-1")
        foreign = {
            "item": str(item_b.pk),
            "lot_serial": str(foreign_lot.pk),
            "source_location": str(qc_zone_b.pk),
            "quarantine_location": str(qc_zone_b.pk),
        }
        data = _qrd_data(item_a, qc_warehouse_a, qc_zone_a)
        data.update({field: foreign[field]})
        before = QuarantineOrder.objects.count()
        form = QuarantineOrderForm(data=data, tenant=tenant_a)
        _assert_foreign_rejected(form, field)
        assert QuarantineOrder.objects.count() == before


# ------------------------------------------------------------------ DefectReportForm


class TestDefectReportForm:
    @pytest.mark.parametrize("field", ["item", "location", "lot_serial", "reported_by", "ncr"])
    def test_crafted_post_foreign_fk_is_field_error(
            self, tenant_a, tenant_b, item_a, item_b, vendor_party_b,
            qc_warehouse_a, qc_zone_b, field):
        """Every tenant-scoped pointer — including the SCM escalation target — refuses a
        foreign pk on its own field; no report is logged."""
        foreign_lot = LotSerial.objects.create(tenant=tenant_b, item=item_b, number="GLO-LOT-2")
        ncr_b = NonConformance.objects.create(
            tenant=tenant_b, title="Foreign finding",
            description="A cross-workspace control row", detected_on=timezone.localdate())
        foreign = {
            "item": str(item_b.pk),
            "location": str(qc_zone_b.pk),
            "lot_serial": str(foreign_lot.pk),
            "reported_by": str(vendor_party_b.pk),
            "ncr": str(ncr_b.pk),
        }
        data = _defect_data(item=str(item_a.pk), location=str(qc_warehouse_a.pk))
        data.update({field: foreign[field]})
        before = DefectReport.objects.count()
        form = DefectReportForm(data=data, tenant=tenant_a)
        _assert_foreign_rejected(form, field)
        assert DefectReport.objects.count() == before

    @pytest.mark.parametrize("filename", ["x.png", "x.jpg"])
    def test_image_uploads_pass_the_allowlist(self, tenant_a, item_a, qc_warehouse_a, filename):
        """Camera-phone captures are the point: png and jpg clear the model's images-only rule
        (asserted at the form boundary; deliberately not saved, so MEDIA_ROOT stays clean)."""
        form = DefectReportForm(
            data=_defect_data(item=str(item_a.pk), location=str(qc_warehouse_a.pk)),
            files={"photo": SimpleUploadedFile(filename, b"\x89PNG fake image bytes")},
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["photo"].name.lower().endswith(("png", "jpg"))

    @pytest.mark.parametrize("filename", ["x.pdf", "x.svg", "x.exe"])
    def test_non_image_uploads_refused_with_image_message(
            self, tenant_a, item_a, qc_warehouse_a, filename):
        """Documents and executables are somebody else's module's job — the report refuses
        them on the photo field with the attach-an-image message, saving nothing."""
        form = DefectReportForm(
            data=_defect_data(item=str(item_a.pk), location=str(qc_warehouse_a.pk)),
            files={"photo": SimpleUploadedFile(filename, b"MZ fake payload")},
            tenant=tenant_a)
        assert not form.is_valid()
        joined = " | ".join(form.errors.get("photo", []))
        assert "not allowed" in joined
        assert "image" in joined
        assert DefectReport.objects.count() == 0

    def test_oversized_upload_refused_with_size_message(self, tenant_a, item_a,
                                                        qc_warehouse_a, monkeypatch):
        """The size cap, exercised against the threshold patched down to 10 bytes so the suite
        never allocates a 20 MB buffer; the message still quotes the real 20 MB ceiling."""
        import apps.inventory.forms.QualityControl.DefectReports as defect_forms
        from apps.inventory.forms._common import MAX_UPLOAD_BYTES

        monkeypatch.setattr(defect_forms, "MAX_UPLOAD_BYTES", 10)
        assert MAX_UPLOAD_BYTES == 20 * 1024 * 1024  # the shared constant is untouched
        form = DefectReportForm(
            data=_defect_data(item=str(item_a.pk), location=str(qc_warehouse_a.pk)),
            files={"photo": SimpleUploadedFile("huge.png", b"x" * 11)},
            tenant=tenant_a)
        assert not form.is_valid()
        joined = " | ".join(form.errors.get("photo", []))
        assert "too large" in joined.lower()
        assert "20 MB" in joined

    def test_photo_url_alone_accepted_without_file(self, tenant_a, item_a, qc_warehouse_a):
        """The external-link pointer stands alone: a valid report with no upload, whose
        lifecycle columns stayed verb-owned (open, numberless until save())."""
        form = DefectReportForm(data=_defect_data(
            item=str(item_a.pk), location=str(qc_warehouse_a.pk),
            photo_url="https://files.example.com/defects/carton.jpg"), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save(commit=False)
        obj.tenant = tenant_a
        obj.save()
        assert obj.number.startswith("DEF-")
        assert obj.photo_url == "https://files.example.com/defects/carton.jpg"
        assert not obj.photo
        assert obj.status == "open"
