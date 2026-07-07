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
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .utils import write_audit_log


def paginate(request, qs, per_page=15):
    page = Paginator(qs, per_page).get_page(request.GET.get("page"))
    # Windowed page list (1 … n-2 n-1 [n] n+1 n+2 … last); None marks an ellipsis gap.
    n, total = page.number, page.paginator.num_pages
    nums = sorted(set([1, total] + list(range(max(1, n - 2), min(total, n + 2) + 1))))
    window, prev = [], 0
    for x in nums:
        if x - prev > 1:
            window.append(None)
        window.append(x)
        prev = x
    page.window = window
    return page


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
            # Map stringified booleans so BooleanField filters work — `.filter(x="False")` would
            # otherwise coerce via bool("False") == True and silently return every row.
            mapped = {"True": True, "False": False}.get(val, val)
            try:
                qs = qs.filter(**{lookup: mapped})
            except (ValueError, ValidationError):
                # L11: a hand-edited/bogus GET value (e.g. ?is_active=abc against a BooleanField)
                # raises inside .filter() itself — skip the filter instead of 500ing.
                continue
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


# Field names whose values must never be written verbatim into AuditLog.changes
# (e.g. bank/account/routing numbers, secrets). Redacted to a placeholder instead.
_SENSITIVE_AUDIT_FIELDS = frozenset({
    "bank_account", "bank_routing", "password", "token", "secret", "api_key",
    "national_id", "passport_number",
    # HRM 3.15 statutory government IDs — redact from the immutable audit trail.
    "uan_number", "pf_number", "esi_number",
    # Confidential manager-only notes (HRM 3.19 PerformanceReview.private_notes / 3.20
    # OneOnOneMeeting.manager_private_notes) — never surfaced to the subject/employee, so must not
    # be copied verbatim into AuditLog.changes either.
    "private_notes", "manager_private_notes",
})


def _changed(form):
    """Compact {field: new_value} of changed fields for the audit log.

    Sensitive fields are redacted so a plaintext account/secret never lands in the
    immutable audit trail (it would otherwise outlive any later encryption-at-rest)."""
    out = {}
    for name in getattr(form, "changed_data", []):
        if name in _SENSITIVE_AUDIT_FIELDS:
            out[name] = "***redacted***"
        else:
            out[name] = str(form.cleaned_data.get(name))[:200]
    return out
