"""core — 0.8 views (privacy & data protection).

Config and evidence surfaces, so they are admin-gated except the read-only computed boards.
"""
import datetime

from django.apps import apps as django_apps
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.privacy import scan_pii_fields, statutory_window_days
from apps.core.models import (
    ConsentPurpose,
    ConsentRecord,
    DataSubjectRequest,
    DisposalRecord,
    PiiClassification,
    RegulatoryFramework,
    RetentionPolicy,
    current_consent,
)
# 0.16 `LegalHold` — imported for ONE purpose: to name the hold that suspends a schedule this board
# would otherwise report as due for disposal. The hold lives in its own model (0.16) and is *not*
# re-declared here (L36); this board is the read side of the integration 0.16 promised.
from apps.core.models.LegalHold import LegalHold
from apps.core.forms import (
    ConsentPurposeForm,
    ConsentRecordForm,
    DataSubjectRequestForm,
    DisposalRecordForm,
    DsarRefusalForm,
    DsarVerificationForm,
    PiiClassificationForm,
    RegulatoryFrameworkForm,
    RetentionPolicyForm,
)


# =============================================================== bullet 1: consent
@tenant_admin_required
def consent_purpose_list(request):
    return crud_list(
        request, ConsentPurpose.objects.filter(tenant=request.tenant).annotate(
            record_count=Count("records")),
        "core/consentpurpose/list.html",
        search_fields=["name", "code", "description"],
        filters=[("lawful_basis", "lawful_basis", False)],
        extra_context={"basis_choices": ConsentPurpose.LAWFUL_BASIS_CHOICES},
    )


@tenant_admin_required
def consent_purpose_create(request):
    return crud_create(request, form_class=ConsentPurposeForm,
                       template="core/consentpurpose/form.html",
                       success_url="core:consent_purpose_list")


@tenant_admin_required
def consent_purpose_edit(request, pk):
    return crud_edit(request, model=ConsentPurpose, pk=pk, form_class=ConsentPurposeForm,
                     template="core/consentpurpose/form.html",
                     success_url="core:consent_purpose_list")


@require_POST
@tenant_admin_required
def consent_purpose_delete(request, pk):
    return crud_delete(request, model=ConsentPurpose, pk=pk,
                       success_url="core:consent_purpose_list")


@tenant_admin_required
def consent_record_list(request):
    return crud_list(
        request,
        ConsentRecord.objects.filter(tenant=request.tenant)
        .select_related("party", "purpose", "recorded_by"),
        "core/consentrecord/list.html",
        search_fields=["party__name", "purpose__name", "evidence"],
        filters=[("action", "action", False), ("source", "source", False),
                 ("purpose", "purpose_id", True)],
        extra_context={"action_choices": ConsentRecord.ACTION_CHOICES,
                       "source_choices": ConsentRecord.SOURCE_CHOICES,
                       "purposes": ConsentPurpose.objects.filter(tenant=request.tenant)},
    )


@tenant_admin_required
def consent_record_create(request):
    """Records ONE event. The actor is stamped, never chosen."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace first.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ConsentRecordForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.recorded_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Consent event recorded.")
            return redirect("core:consent_record_list")
    else:
        form = ConsentRecordForm(tenant=request.tenant)
    return render(request, "core/consentrecord/form.html", {"form": form})


@tenant_admin_required
@require_POST
def consent_record_delete(request, pk):
    """Deleting a consent event is allowed but audited — it is a correction of a mis-keyed record,
    and the audit row is what keeps that honest."""
    return crud_delete(request, model=ConsentRecord, pk=pk,
                       success_url="core:consent_record_list")


@tenant_admin_required
def consent_matrix(request):
    """COMPUTED: each party's EFFECTIVE state per purpose. No table.

    Derived from the latest event per (party, purpose), so a withdrawal cannot fail to update a
    stored flag — there is no flag. Only parties with at least one event are listed: the matrix
    reports consent, it does not invent a row for everyone who was never asked.
    """
    purposes = list(ConsentPurpose.objects.filter(tenant=request.tenant, is_active=True))
    records = (ConsentRecord.objects.filter(tenant=request.tenant)
               .select_related("party", "purpose").order_by("-occurred_at", "-id"))
    # Latest event per (party, purpose) — one pass, then read.
    latest = {}
    for rec in records:
        key = (rec.party_id, rec.purpose_id)
        if key not in latest:
            latest[key] = rec
    party_ids = sorted({p for (p, _) in latest})
    parties = {p.pk: p for p in Party.objects.filter(tenant=request.tenant, pk__in=party_ids)}

    rows = []
    for pid in party_ids:
        cells = []
        for purpose in purposes:
            rec = latest.get((pid, purpose.pk))
            if rec is None:
                state = "unknown"
            elif rec.expires_at is not None and rec.expires_at <= timezone.now():
                state = "expired"
            else:
                state = rec.action
            cells.append({"purpose": purpose, "state": state, "record": rec})
        rows.append({"party": parties.get(pid), "cells": cells})

    granted = sum(1 for r in latest.values()
                  if r.action == "granted" and (r.expires_at is None or r.expires_at > timezone.now()))
    context = {
        "purposes": purposes,
        "rows": rows,
        "granted_count": granted,
        "withdrawn_count": sum(1 for r in latest.values() if r.action == "withdrawn"),
        "purpose_count": len(purposes),
    }
    return render(request, "core/consentmatrix.html", context)


# =============================================================== bullet 2: DSAR
@tenant_admin_required
def dsar_list(request):
    return crud_list(
        request,
        DataSubjectRequest.objects.filter(tenant=request.tenant)
        .select_related("subject", "handled_by"),
        "core/dsar/list.html",
        search_fields=["subject__name", "detail"],
        filters=[("status", "status", False), ("kind", "kind", False)],
        extra_context={"status_choices": DataSubjectRequest.STATUS_CHOICES,
                       "kind_choices": DataSubjectRequest.KIND_CHOICES},
    )


@tenant_admin_required
def dsar_detail(request, pk):
    obj = get_object_or_404(DataSubjectRequest.objects.select_related("subject", "handled_by"),
                            pk=pk, tenant=request.tenant)
    return render(request, "core/dsar/detail.html", {
        "obj": obj,
        "verification_form": DsarVerificationForm(initial={"verification_note": obj.verification_note,
                                                            "response_notes": obj.response_notes}),
        "refusal_form": DsarRefusalForm(initial={"refusal_reason": obj.refusal_reason}),
    })


@tenant_admin_required
def dsar_create(request):
    """Stamps `due_at` from the workspace's enabled frameworks at creation.

    `statutory_window_days` returns None when nothing is enabled, and the request is then recorded
    with NO deadline rather than an invented one — a deadline the workspace cannot point at a regime
    for is a fabricated obligation.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace first.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = DataSubjectRequestForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            window = statutory_window_days(request.tenant)
            if window is not None:
                obj.due_at = obj.received_at + datetime.timedelta(days=window)
            obj.save()
            write_audit_log(request.user, obj, "create")
            if window is None:
                messages.warning(request, "No regulatory framework is enabled, so this request has "
                                          "NO statutory deadline. Enable one to start the clock.")
            else:
                messages.success(request, f"Logged with a {window}-day statutory window.")
            return redirect("core:dsar_detail", pk=obj.pk)
    else:
        form = DataSubjectRequestForm(tenant=request.tenant)
    return render(request, "core/dsar/form.html", {"form": form})


@tenant_admin_required
def dsar_edit(request, pk):
    obj = get_object_or_404(DataSubjectRequest, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(request, "A closed request is frozen evidence and cannot be edited.")
        return redirect("core:dsar_detail", pk=obj.pk)
    return crud_edit(request, model=DataSubjectRequest, pk=pk, form_class=DataSubjectRequestForm,
                     template="core/dsar/form.html", success_url="core:dsar_list")


@require_POST
@tenant_admin_required
def dsar_delete(request, pk):
    obj = get_object_or_404(DataSubjectRequest, pk=pk, tenant=request.tenant)
    if obj.status in ("completed", "refused"):
        messages.error(request, "A completed or refused request is the evidence of how it was "
                                "answered and cannot be deleted.")
        return redirect("core:dsar_detail", pk=obj.pk)
    return crud_delete(request, model=DataSubjectRequest, pk=pk, success_url="core:dsar_list")


@require_POST
@tenant_admin_required
def dsar_verify(request, pk):
    """THE GATE. Nothing else may progress a request until identity is verified.

    Releasing or erasing personal data on an unverified request is the failure this sub-module exists
    to prevent, so this is a verb with a required note rather than a checkbox on the create form.
    """
    obj = get_object_or_404(DataSubjectRequest, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(request, "That request is already closed.")
        return redirect("core:dsar_detail", pk=obj.pk)
    form = DsarVerificationForm(request.POST)
    if not form.is_valid():
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
        return redirect("core:dsar_detail", pk=obj.pk)
    obj.identity_verified = True
    obj.verification_note = form.cleaned_data["verification_note"]
    obj.response_notes = form.cleaned_data["response_notes"] or obj.response_notes
    if obj.status in ("received", "verifying"):
        obj.status = "in_progress"
    obj.save(update_fields=["identity_verified", "verification_note", "response_notes", "status"])
    write_audit_log(request.user, obj, "update", changes={"verb": "dsar_verify"})
    messages.success(request, "Identity verified — the request may now proceed.")
    return redirect("core:dsar_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def dsar_complete(request, pk):
    obj = get_object_or_404(DataSubjectRequest, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(request, "That request is already closed.")
        return redirect("core:dsar_detail", pk=obj.pk)
    if not obj.identity_verified:
        messages.error(request, "Verify the requester's identity before completing this request.")
        return redirect("core:dsar_detail", pk=obj.pk)
    obj.status = "completed"
    obj.completed_at = timezone.now()
    obj.handled_by = request.user
    obj.save(update_fields=["status", "completed_at", "handled_by"])
    write_audit_log(request.user, obj, "update", changes={"verb": "dsar_complete"})
    messages.success(request, "Request completed.")
    return redirect("core:dsar_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def dsar_refuse(request, pk):
    """A refusal must cite a ground."""
    obj = get_object_or_404(DataSubjectRequest, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(request, "That request is already closed.")
        return redirect("core:dsar_detail", pk=obj.pk)
    form = DsarRefusalForm(request.POST)
    if not form.is_valid():
        messages.error(request, "A refusal needs a stated lawful ground.")
        return redirect("core:dsar_detail", pk=obj.pk)
    obj.status = "refused"
    obj.refusal_reason = form.cleaned_data["refusal_reason"]
    obj.completed_at = timezone.now()
    obj.handled_by = request.user
    obj.save(update_fields=["status", "refusal_reason", "completed_at", "handled_by"])
    write_audit_log(request.user, obj, "update", changes={"verb": "dsar_refuse"})
    messages.success(request, "Request refused, with the ground recorded.")
    return redirect("core:dsar_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def dsar_withdraw(request, pk):
    obj = get_object_or_404(DataSubjectRequest, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(request, "That request is already closed.")
        return redirect("core:dsar_detail", pk=obj.pk)
    obj.status = "withdrawn"
    obj.completed_at = timezone.now()
    obj.handled_by = request.user
    obj.save(update_fields=["status", "completed_at", "handled_by"])
    write_audit_log(request.user, obj, "update", changes={"verb": "dsar_withdraw"})
    messages.success(request, "Request marked withdrawn by the subject.")
    return redirect("core:dsar_detail", pk=obj.pk)


# =============================================================== bullet 3: retention
@tenant_admin_required
def retention_policy_list(request):
    return crud_list(
        request, RetentionPolicy.objects.filter(tenant=request.tenant),
        "core/retentionpolicy/list.html",
        search_fields=["name", "data_category", "model_label"],
        filters=[("action", "action", False), ("basis", "basis", False)],
        extra_context={"action_choices": RetentionPolicy.ACTION_CHOICES,
                       "basis_choices": RetentionPolicy.BASIS_CHOICES},
    )


@tenant_admin_required
def retention_policy_create(request):
    return crud_create(request, form_class=RetentionPolicyForm,
                       template="core/retentionpolicy/form.html",
                       success_url="core:retention_policy_list")


@tenant_admin_required
def retention_policy_edit(request, pk):
    return crud_edit(request, model=RetentionPolicy, pk=pk, form_class=RetentionPolicyForm,
                     template="core/retentionpolicy/form.html",
                     success_url="core:retention_policy_list")


@require_POST
@tenant_admin_required
def retention_policy_delete(request, pk):
    return crud_delete(request, model=RetentionPolicy, pk=pk,
                       success_url="core:retention_policy_list")


@tenant_admin_required
def disposal_list(request):
    return crud_list(
        request,
        DisposalRecord.objects.filter(tenant=request.tenant).select_related("policy", "performed_by"),
        "core/disposal/list.html",
        search_fields=["model_label", "evidence", "notes"],
        filters=[("method", "method", False)],
        extra_context={"method_choices": DisposalRecord.METHOD_CHOICES},
    )


@tenant_admin_required
def disposal_create(request):
    return crud_create(request, form_class=DisposalRecordForm,
                       template="core/disposal/form.html",
                       success_url="core:disposal_list")


@tenant_admin_required
def retention_board(request):
    """COMPUTED: what each active policy would dispose of. No table, and NO destruction.

    For a policy pinned to a model, counts rows older than the retention window — but ONLY when that
    model actually has a `created_at`. Where it does not, the row says so instead of reporting 0,
    because a zero that means "cannot tell" is the most dangerous number a compliance board can show.

    **A legal hold SUSPENDS the schedule covering its scope (0.16).** Reporting "N due for disposal" for
    a scope under an active hold would be the same false all-clear in a worse direction: the number would
    invite the disposal of data a court order protects, which is spoliation. So a held policy reports NO
    count at all and names the hold instead. The match is `LegalHold.suspends_policy()`, which tests the
    policy FK **or** the model label — the two ways a hold may be pinned.
    """
    policies = RetentionPolicy.objects.filter(tenant=request.tenant, is_active=True)
    # Read once, in the view, then match in Python: `suspends_policy()` compares FKs and needs no query,
    # and doing it here rather than per-row keeps this to two queries regardless of policy count.
    holds = list(LegalHold.active_for_tenant(request.tenant))
    rows = []
    for policy in policies:
        due = None
        note = ""
        held_by = [h for h in holds if h.suspends_policy(policy)]
        if held_by:
            # Named, never counted. The hold's scope and matter reference are what make the suspension
            # actionable; a bare "on hold" would leave the reader unable to find out why.
            names = ", ".join(h.name for h in held_by)
            note = ("Suspended by an active legal hold (%s). Nothing may be disposed of in this scope "
                    "while the hold is in force, so no count is reported." % names)
        elif not policy.model_label:
            note = "No model pinned — this policy is a category, not a computable schedule."
        else:
            try:
                app_label, model_name = policy.model_label.split(".")
                model = django_apps.get_model(app_label, model_name)
            except (ValueError, LookupError):
                note = "Model not found — check the label."
                model = None
            if model is not None:
                names = {f.name for f in model._meta.concrete_fields}
                if "created_at" not in names:
                    note = ("This model has no created_at column, so an age cannot be computed. "
                            "Reporting 0 here would be a false all-clear.")
                elif "tenant" in names:
                    cutoff = timezone.now() - datetime.timedelta(days=30 * policy.retention_months)
                    due = model.objects.filter(tenant=request.tenant, created_at__lt=cutoff).count()
                else:
                    note = "This model has no tenant column, so nothing here is attributable."
        rows.append({"policy": policy, "due": due, "note": note, "held_by": held_by})
    held_rows = [r for r in rows if r["held_by"]]
    context = {
        "rows": rows,
        "computable": sum(1 for r in rows if r["due"] is not None),
        "total_due": sum(r["due"] for r in rows if r["due"] is not None),
        "disposals": DisposalRecord.objects.filter(tenant=request.tenant).count(),
        # Surfaced explicitly rather than left for the reader to infer from the note text: a board that
        # silently drops a policy out of `computable` looks like a board with nothing to say.
        "held_count": len(held_rows),
        "held_names": ", ".join(sorted({h.name for r in held_rows for h in r["held_by"]})),
    }
    return render(request, "core/retentionboard.html", context)


# =============================================================== bullet 4: PII map
@tenant_admin_required
def pii_map(request):
    return crud_list(
        request,
        PiiClassification.objects.filter(tenant=request.tenant).select_related("reviewed_by"),
        "core/pii/list.html",
        search_fields=["model_label", "field_name", "notes"],
        filters=[("category", "category", False), ("sensitivity", "sensitivity", False),
                 ("confirmation", "confirmation", False)],
        extra_context={"category_choices": PiiClassification.CATEGORY_CHOICES,
                       "sensitivity_choices": PiiClassification.SENSITIVITY_CHOICES,
                       "confirmation_choices": PiiClassification.CONFIRMATION_CHOICES},
    )


@require_POST
@tenant_admin_required
def pii_scan(request):
    """Populate the data map from the schema heuristic. Idempotent and NON-DESTRUCTIVE.

    A row a human has already `confirmed` or `dismissed` is NEVER touched — re-running the scan must
    not silently revert a judgement someone made, or the map becomes untrustworthy and then unused.
    """
    existing = {(r.model_label, r.field_name): r
                for r in PiiClassification.objects.filter(tenant=request.tenant)}
    created = updated = preserved = 0
    for model_label, field_name, category, sensitivity in scan_pii_fields():
        row = existing.get((model_label, field_name))
        if row is None:
            PiiClassification.objects.create(
                tenant=request.tenant, model_label=model_label, field_name=field_name,
                category=category, sensitivity=sensitivity, confirmation="suggested",
            )
            created += 1
        elif row.confirmation == "suggested":
            row.category = category
            row.sensitivity = sensitivity
            row.save(update_fields=["category", "sensitivity"])
            updated += 1
        else:
            preserved += 1
    write_audit_log(request.user, None, "create",
                    changes={"verb": "pii_scan", "created": created, "updated": updated,
                             "preserved": preserved})
    messages.success(request, f"Scan complete: {created} new, {updated} refreshed, "
                              f"{preserved} human decisions preserved.")
    return redirect("core:pii_map")


@tenant_admin_required
def pii_classify(request, pk):
    """The human confirmation step."""
    obj = get_object_or_404(PiiClassification, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = PiiClassificationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            row = form.save(commit=False)
            row.reviewed_by = request.user
            row.reviewed_at = timezone.now()
            row.save()
            write_audit_log(request.user, row, "update", changes={"verb": "pii_classify"})
            messages.success(request, "Classification recorded.")
            return redirect("core:pii_map")
    else:
        form = PiiClassificationForm(instance=obj, tenant=request.tenant)
    return render(request, "core/pii/form.html", {"form": form, "obj": obj})


# =============================================================== bullet 5: frameworks
@tenant_admin_required
def regulatory_list(request):
    return crud_list(
        request, RegulatoryFramework.objects.filter(tenant=request.tenant),
        "core/regulatory/list.html",
        search_fields=["code", "label", "notes"],
        filters=[("enabled", "is_enabled", False)],
        extra_context={"enabled_choices": [("True", "Enabled"), ("False", "Disabled")],
                       "strictest_window": statutory_window_days(request.tenant)},
    )


@require_POST
@tenant_admin_required
def regulatory_sync(request):
    """Create a row for every framework code the app knows, disabled by default.

    Disabled on purpose: a workspace claiming HIPAA because a seeder said so would be a compliance
    lie. Enabling one is an explicit act that also starts the DSAR clock.
    """
    existing = set(RegulatoryFramework.objects.filter(tenant=request.tenant)
                   .values_list("code", flat=True))
    created = 0
    for code, label in RegulatoryFramework.CODE_CHOICES:
        if code in existing:
            continue
        RegulatoryFramework.objects.create(tenant=request.tenant, code=code, label=label,
                                           is_enabled=False)
        created += 1
    write_audit_log(request.user, None, "create",
                    changes={"verb": "regulatory_sync", "created": created})
    messages.success(request, f"Added {created} framework row(s), all disabled. Enable the ones "
                              "this workspace actually operates under.")
    return redirect("core:regulatory_list")


@tenant_admin_required
def regulatory_edit(request, pk):
    return crud_edit(request, model=RegulatoryFramework, pk=pk, form_class=RegulatoryFrameworkForm,
                     template="core/regulatory/form.html", success_url="core:regulatory_list")


@tenant_admin_required
def privacy_overview(request):
    """COMPUTED hub for 0.8 — no table. Reports posture and names what is NOT built."""
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Privacy posture applies to a tenant workspace.")
        return redirect("dashboard:home")
    dsars = DataSubjectRequest.objects.filter(tenant=tenant)
    pii = PiiClassification.objects.filter(tenant=tenant)
    context = {
        "purpose_count": ConsentPurpose.objects.filter(tenant=tenant, is_active=True).count(),
        "consent_events": ConsentRecord.objects.filter(tenant=tenant).count(),
        "open_dsars": dsars.filter(status__in=["received", "verifying", "in_progress"]).count(),
        "overdue_dsars": sum(1 for d in dsars if d.is_overdue),
        "total_dsars": dsars.count(),
        "policy_count": RetentionPolicy.objects.filter(tenant=tenant, is_active=True).count(),
        "disposal_count": DisposalRecord.objects.filter(tenant=tenant).count(),
        "pii_total": pii.count(),
        "pii_confirmed": pii.filter(confirmation="confirmed").count(),
        "pii_dismissed": pii.filter(confirmation="dismissed").count(),
        "pii_high": pii.filter(sensitivity="high").exclude(confirmation="dismissed").count(),
        "frameworks": RegulatoryFramework.objects.filter(tenant=tenant, is_enabled=True),
        "strictest_window": statutory_window_days(tenant),
        "recent_dsars": dsars.select_related("subject")[:8],
    }
    return render(request, "core/privacyoverview.html", context)
