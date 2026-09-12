"""Projects 7.7 — ScopeItem views: the boundary / assumption / constraint registry and its verbs.

``crud_list``'s ``filters`` are field lookups only, so the two derived lenses are **pre-scoped
here** on real columns: ``?boundaries=1`` (the in-scope / out-of-scope rows — the registry's
boundary slice, driven by the model's own ``BOUNDARY_TYPES``) and ``?open=1`` (still live).

Verbs (POST-only, GET → 405): ``validate`` (a member confirms the assumption/constraint holds),
``realize`` and ``retire`` (the item closed — each binds ``ScopeItemOutcomeForm`` so the row keeps
the narrative that closed it, and each stamps ``closed_at`` in the same request).
"""
from apps.core.crud import as_db_int
from apps.projects.forms import ScopeItemForm, ScopeItemOutcomeForm
from apps.projects.models import ScopeItem
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (
    get_object_or_404,
    login_required,
    redirect,
    render,
    require_POST,
)
from apps.projects.views._helpers import owners, projects

_LOCKED_MSG = ("A realized or retired registry row is closed evidence and cannot be edited or "
               "deleted.")


@login_required
def sci_list(request):
    qs = (ScopeItem.objects.filter(tenant=request.tenant)
          .select_related("project", "requirement", "owner"))
    if request.GET.get("boundaries") == "1":
        qs = qs.filter(item_type__in=sorted(ScopeItem.BOUNDARY_TYPES))
    if request.GET.get("open") == "1":
        qs = qs.filter(status__in=("open", "validated"))
    return crud_list(
        request, qs, "projects/scope/scopeitem/list.html",
        search_fields=["number", "statement", "description", "outcome"],
        filters=[("project", "project_id", True),
                 ("item_type", "item_type", False),
                 ("status", "status", False),
                 ("impact_area", "impact_area", False),
                 ("owner", "owner_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "type_choices": ScopeItem.ITEM_TYPE_CHOICES,
            "status_choices": ScopeItem.STATUS_CHOICES,
            "impact_choices": ScopeItem.IMPACT_AREA_CHOICES,
            "owners": owners(request.tenant),
        },
    )


@login_required
def sci_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ScopeItemForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Scope item {obj.number} logged.")
            return redirect("projects:sci_detail", pk=obj.pk)
    else:
        form = ScopeItemForm(tenant=request.tenant,
                             initial={"project": as_db_int(request.GET.get("project", ""))})
    return render(request, "projects/scope/scopeitem/form.html",
                  {"form": form, "is_edit": False})


@login_required
def sci_detail(request, pk):
    obj = get_object_or_404(
        ScopeItem.objects.select_related("project", "requirement", "owner", "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/scope/scopeitem/detail.html", {
        "obj": obj,
        "outcome_form": ScopeItemOutcomeForm(),
    })


@login_required
def sci_edit(request, pk):
    obj = get_object_or_404(ScopeItem, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:sci_detail", pk=obj.pk)
    return crud_edit(
        request, model=ScopeItem, pk=pk, form_class=ScopeItemForm,
        template="projects/scope/scopeitem/form.html", success_url="projects:sci_list")


@login_required
@require_POST
def sci_delete(request, pk):
    obj = get_object_or_404(ScopeItem, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:sci_detail", pk=obj.pk)
    return crud_delete(request, model=ScopeItem, pk=pk, success_url="projects:sci_list")


# -- lifecycle verbs ----------------------------------------------------------------------------

@login_required
@require_POST
def sci_validate(request, pk):
    """A member confirms the assumption holds / the constraint still stands. No narrative needed."""
    obj = get_object_or_404(ScopeItem, pk=pk, tenant=request.tenant)
    if obj.status != "open":
        messages.error(request, "Only an open registry row can be validated.")
        return redirect("projects:sci_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "validated"
    obj.save(update_fields=["status", "updated_at"])
    # ``AuditLog.action`` is varchar(10) and "validated" is 9 characters — but the app's verb
    # vocabulary writes the transition verb in ``changes`` and keeps ``action`` to the small
    # audited set, so the action string is "submit" (the row advanced a gate) and the verb in
    # ``changes`` is "validate".
    write_audit_log(request.user, obj, "submit",
                    changes={"verb": "validate", "from": previous, "to": obj.status})
    messages.success(request, f"Validated {obj.number}.")
    return redirect("projects:sci_detail", pk=obj.pk)


@login_required
@require_POST
def sci_realize(request, pk):
    """The assumption came to pass / the constraint bit. Binds the outcome narrative."""
    obj = get_object_or_404(ScopeItem, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(request, "Only an open or validated registry row can be realized.")
        return redirect("projects:sci_detail", pk=obj.pk)
    form = ScopeItemOutcomeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Realizing a registry row needs a written outcome.")
        return redirect("projects:sci_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "realized"
    obj.outcome = form.cleaned_data["outcome"]
    obj.closed_at = timezone.now()
    obj.save(update_fields=["status", "outcome", "closed_at", "updated_at"])
    write_audit_log(request.user, obj, "realize",
                    changes={"verb": "realize", "from": previous, "to": obj.status})
    messages.success(request, f"Realized {obj.number}.")
    return redirect("projects:sci_detail", pk=obj.pk)


@login_required
@require_POST
def sci_retire(request, pk):
    """Retire the row — the boundary moved or the assumption stopped mattering. Binds the outcome."""
    obj = get_object_or_404(ScopeItem, pk=pk, tenant=request.tenant)
    if obj.status == "retired":
        messages.info(request, "That registry row is already retired.")
        return redirect("projects:sci_detail", pk=obj.pk)
    if not obj.is_open:
        messages.error(request, "Only an open or validated registry row can be retired.")
        return redirect("projects:sci_detail", pk=obj.pk)
    form = ScopeItemOutcomeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Retiring a registry row needs a written outcome.")
        return redirect("projects:sci_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "retired"
    obj.outcome = form.cleaned_data["outcome"]
    obj.closed_at = timezone.now()
    obj.save(update_fields=["status", "outcome", "closed_at", "updated_at"])
    write_audit_log(request.user, obj, "retire",
                    changes={"verb": "retire", "from": previous, "to": obj.status})
    messages.success(request, f"Retired {obj.number}.")
    return redirect("projects:sci_detail", pk=obj.pk)
