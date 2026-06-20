"""Reusable, tenant-safe CRUD helpers shared by every foundation app.

Centralizing list/create/edit/detail/delete here fixes the recurring traps once for
all modules: search, the int-FK filter guard (L11), pagination (L9 — Paginator pages
guard prev/next), tenant scoping, and audit logging. Per-model views stay thin and
declare only their own search fields + filter spec.

Context-var contract (pinned, L7):
  * list  -> ``object_list`` + ``page_obj`` + ``q`` (+ the view's filter choices)
  * detail/edit object -> ``obj``
  * form  -> ``form`` + ``is_edit``
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .utils import write_audit_log


def paginate(request, qs, per_page=15):
    return Paginator(qs, per_page).get_page(request.GET.get("page"))


def apply_search(qs, q, fields):
    if q and fields:
        cond = Q()
        for field in fields:
            cond |= Q(**{f"{field}__icontains": q})
        qs = qs.filter(cond)
    return qs


def crud_list(request, qs, template, *, search_fields=(), filters=(), extra_context=None, per_page=15):
    """``filters`` = iterable of ``(get_param, orm_lookup, is_int)`` tuples."""
    q = request.GET.get("q", "").strip()
    qs = apply_search(qs, q, search_fields)
    for param, lookup, is_int in filters:
        val = request.GET.get(param, "").strip()
        if not val:
            continue
        if is_int:
            if val.isdigit():  # L11: never pass non-numeric to an int FK filter
                qs = qs.filter(**{lookup: int(val)})
        else:
            qs = qs.filter(**{lookup: val})
    page_obj = paginate(request, qs, per_page)
    ctx = {"object_list": page_obj.object_list, "page_obj": page_obj, "q": q}
    ctx.update(extra_context or {})
    return render(request, template, ctx)


def crud_create(request, *, form_class, template, success_url, extra_context=None,
                set_tenant=True, audit=True):
    # A tenant-less user (e.g. the superuser, tenant=None) must not create orphan rows.
    if set_tenant and request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if set_tenant and hasattr(obj, "tenant_id"):
                obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            if audit:
                write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect(success_url)
    else:
        form = form_class(tenant=request.tenant)
    ctx = {"form": form, "is_edit": False}
    ctx.update(extra_context or {})
    return render(request, template, ctx)


def crud_edit(request, *, model, pk, form_class, template, success_url, extra_context=None,
              audit=True):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            if audit:
                write_audit_log(request.user, obj, "update", changes=_changed(form))
            messages.success(request, "Updated successfully.")
            return redirect(success_url)
    else:
        form = form_class(instance=obj, tenant=request.tenant)
    ctx = {"form": form, "obj": obj, "is_edit": True}
    ctx.update(extra_context or {})
    return render(request, template, ctx)


def crud_detail(request, *, model, pk, template, extra_context=None, select_related=()):
    qs = model.objects.filter(tenant=request.tenant)
    if select_related:
        qs = qs.select_related(*select_related)
    obj = get_object_or_404(qs, pk=pk)
    ctx = {"obj": obj}
    ctx.update(extra_context or {})
    return render(request, template, ctx)


def crud_delete(request, *, model, pk, success_url, audit=True):
    # Self-defending: only mutate on POST even if a caller forgets @require_POST.
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        if audit:
            write_audit_log(request.user, obj, "delete")
        obj.delete()
        messages.success(request, "Deleted successfully.")
    return redirect(success_url)


def _changed(form):
    """Compact {field: new_value} of changed fields for the audit log."""
    out = {}
    for name in getattr(form, "changed_data", []):
        out[name] = str(form.cleaned_data.get(name))[:200]
    return out
