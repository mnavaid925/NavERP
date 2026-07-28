"""SCM 4.9 Quality Management — InspectionPlan views (the criteria master + its characteristics).

Master-data CRUD, so everything here is ``@login_required``: nothing in this file moves stock or
advances a document's state. The one thing worth reading is ``_inspectionplan_form``, which saves
the header and the characteristic formset in ONE transaction and — critically — attaches the
cleaned header to the formset BEFORE validating it.
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _item_qs, _need_tenant, _supplier_parties
from apps.scm.models import InspectionPlan, ItemCategory
from apps.scm.forms import InspectionCharacteristicFormSet, InspectionPlanForm


@login_required
def inspectionplan_list(request):
    qs = (InspectionPlan.objects.filter(tenant=request.tenant)
          .select_related("item", "item_category", "supplier")
          .annotate(characteristic_count=Count("characteristics", distinct=True))
          # Explicit order_by: annotate() sets a GROUP BY, which makes QuerySet.ordered report
          # False even though Meta.ordering still reaches the SQL — enough for the paginator to
          # emit UnorderedObjectListWarning on every page load (4.8 finding).
          .order_by("code", "version"))
    return crud_list(
        request, qs, "scm/quality/inspectionplan/list.html",
        search_fields=["code", "name", "notes", "version", "item__sku", "item__name"],
        filters=[("plan_type", "plan_type", False), ("item", "item_id", True),
                 ("item_category", "item_category_id", True), ("supplier", "supplier_id", True),
                 ("sampling_method", "sampling_method", False), ("is_active", "is_active", False)],
        extra_context={
            "type_choices": InspectionPlan.PLAN_TYPE_CHOICES,
            "sampling_choices": InspectionPlan.SAMPLING_METHOD_CHOICES,
            "items": _item_qs(request.tenant),
            "categories": ItemCategory.objects.filter(tenant=request.tenant),
            "suppliers": _supplier_parties(request.tenant),
        },
    )


@login_required
def inspectionplan_create(request):
    return _inspectionplan_form(request, instance=None)


@login_required
def inspectionplan_edit(request, pk):
    obj = get_object_or_404(InspectionPlan, pk=pk, tenant=request.tenant)
    return _inspectionplan_form(request, instance=obj)


def _inspectionplan_form(request, instance):
    """Header + characteristic formset in ONE transaction.

    A plan that saved its header but lost its characteristics would be a plan that produces an
    empty inspection — so the two commit together or not at all.

    ``formset.instance = form.instance`` before ``formset.is_valid()`` is load-bearing, not
    tidiness: on create the view passes ``instance=None``, so BaseInlineFormSet substitutes an
    empty ``InspectionPlan()`` and the formset's audit-checklist rule (which reads the parent's
    ``plan_type``) would compare against the field default instead of what was just submitted. That
    exact omission shipped as a live data-corruption bug in 4.8's BOM form.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:inspectionplan_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = InspectionPlanForm(request.POST, instance=instance, tenant=request.tenant)
        formset = InspectionCharacteristicFormSet(request.POST, instance=instance,
                                                  form_kwargs={"tenant": request.tenant})
        form_ok = form.is_valid()
        if form_ok:
            formset.instance = form.instance
        if form_ok and formset.is_valid():
            with transaction.atomic():
                plan = form.save(commit=False)
                plan.tenant = request.tenant
                plan.save()
                formset.instance = plan
                formset.save()
            # crud_* is bypassed here so the formset can commit with its parent — which means
            # nothing logs automatically. Hand-roll it rather than lose the edit diff.
            write_audit_log(request.user, plan, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Inspection plan {plan.code} v{plan.version} saved.")
            return redirect("scm:inspectionplan_detail", pk=plan.pk)
    else:
        form = InspectionPlanForm(instance=instance, tenant=request.tenant)
        formset = InspectionCharacteristicFormSet(instance=instance,
                                                  form_kwargs={"tenant": request.tenant})
    return render(request, "scm/quality/inspectionplan/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def inspectionplan_detail(request, pk):
    obj = get_object_or_404(
        InspectionPlan.objects.select_related("item", "item_category", "supplier"),
        pk=pk, tenant=request.tenant)
    return render(request, "scm/quality/inspectionplan/detail.html", {
        "obj": obj,
        "characteristics": obj.characteristics.select_related("uom").all(),
        "is_effective_now": obj.is_effective(),
        # Capped: a long-lived plan accumulates inspections indefinitely, and this panel is a
        # "what has this been used for" sample, not a report.
        "inspections": (obj.inspections.select_related("item", "lot_serial__item", "inspector")
                        .order_by("-inspected_on", "-id")[:10]),
        "audits": obj.audits.select_related("auditee_party", "auditee_org_unit")[:10],
    })


@login_required
@require_POST
def inspectionplan_delete(request, pk):
    obj = get_object_or_404(InspectionPlan, pk=pk, tenant=request.tenant)
    # QualityInspection.plan and QualityAudit.checklist_plan are both SET_NULL, so deleting would
    # silently orphan the link on historical documents rather than error. Refuse it — the
    # provenance of a certificate is worth more than the tidy-up (the billofmaterials_delete
    # precedent).
    if obj.inspections.exists():
        messages.error(request, "This plan has been used by inspections and cannot be deleted — "
                                "deactivate it instead.")
        return redirect("scm:inspectionplan_detail", pk=pk)
    if obj.audits.exists():
        messages.error(request, "This plan is the checklist for one or more audits and cannot be "
                                "deleted — deactivate it instead.")
        return redirect("scm:inspectionplan_detail", pk=pk)
    return crud_delete(request, model=InspectionPlan, pk=pk, success_url="scm:inspectionplan_list")
