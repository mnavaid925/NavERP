"""core — 0.21 views: the compliance posture board and the four 0.21 registers.

**The posture every view here takes, inherited verbatim from 0.20's `AdminConsole.py`:** NavERP
enforces nothing. A control marked `effective` is a sentence somebody typed; an acknowledgement row
is a record that somebody pressed save; nothing reminds anybody of anything, because there is no
mail dispatcher. **Every success message on this page says "recorded"**, never "enforced",
"granted", "reminded" or "verified", and `GRC_NOTES` is printed verbatim on every 0.21 page so a
page and its board cannot disagree about what this application can and cannot do.

**The zero rule**, restated because it is the one that matters here: a figure this application
cannot determine is an em dash or an explicit "not measured", never `0`. `acknowledgement_rate`
returns `None` (not `0`) when there is nobody to acknowledge against, and the templates print an
em dash for it. A compliance board that reports "0% acknowledged" of nobody is making a false
statement about a workspace rather than a measurement of one.

**Every guard lives in the view, never only in a hidden button.** The two actions re-read the row
with `tenant=request.tenant` and refuse a contradictory state *before* writing anything, so a
hand-made POST cannot reach them and no audit row is written either. That is the 0.16
`backup_job_verify` ruling: refusing in the template would leave the action reachable and unaudited.

**`@require_POST` sits ABOVE the role gate on purpose** — decorators apply bottom-up, so the
outermost runs first. With the role gate outermost a member's GET would be answered 403 before the
method check ran, and the house standard is 405 for a wrong method regardless of role.
"""
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.crud import as_db_int
from apps.core.utils import write_audit_log
from apps.core.models import (
    ComplianceControl,
    ControlFramework,
    ControlFrameworkMapping,
    CorporatePolicy,
    PolicyAcknowledgement,
    RiskRegister,
)
from apps.core.forms import (
    ComplianceControlForm,
    ControlFrameworkForm,
    ControlFrameworkMappingForm,
    CorporatePolicyForm,
    PolicyAcknowledgementForm,
    RiskRegisterForm,
)


#: The honest-limit lines every 0.21 page prints. A module-level constant so a page and its board
#: cannot disagree about what this application can and cannot do — the 0.20 `OPS_NOTES` pattern.
GRC_NOTES = [
    "This is a register of declared intent, not a runtime. No page here enforces a control, grants "
    "an auditor access, pins data to a region, or reminds anyone to acknowledge a policy.",
    "`implemented` / `effective` / `covered` are statements a person made. Nothing in NavERP checks "
    "them, and no control gates any action anywhere in this application.",
    "NavERP is a single-region Django application with one database. A data-residency row would "
    "record where data is declared to live, not where it is.",
    "An acknowledgement row is a record that somebody pressed save. There is no mail dispatcher in "
    "this application, so nobody is ever reminded.",
]



# ============================================================ bullet 1: control frameworks
@tenant_admin_required
def controlframework_list(request):
    # I7: select_related("owner") -- the list renders the owner column, so without it that is
    # one extra query per row.
    qs = ControlFramework.objects.filter(tenant=request.tenant).select_related("owner")
    return crud_list(
        request, qs, "core/controlframework/list.html",
        search_fields=["code", "name", "authority", "description"],
        filters=[("type", "framework_type", False), ("is_active", "is_active", False)],
        extra_context={
            "type_choices": ControlFramework.FRAMEWORK_TYPE_CHOICES,
            "framework_count": qs.count(),
            "mapping_count": ControlFrameworkMapping.objects.filter(
                tenant=request.tenant).count(),
            "notes": GRC_NOTES,
        },
    )


@tenant_admin_required
def controlframework_create(request):
    return crud_create(
        request, form_class=ControlFrameworkForm, template="core/controlframework/form.html",
        success_url="core:controlframework_list", extra_context={"notes": GRC_NOTES})


@tenant_admin_required
def controlframework_detail(request, pk):
    framework = get_object_or_404(ControlFramework, pk=pk, tenant=request.tenant)
    return render(request, "core/controlframework/detail.html", {
        "obj": framework,
        "mappings": framework.mappings.select_related("control").order_by("control__code"),
        "control_count": framework.mappings.count(),
        "notes": GRC_NOTES,
    })


@tenant_admin_required
def controlframework_edit(request, pk):
    return crud_edit(
        request, model=ControlFramework, pk=pk, form_class=ControlFrameworkForm,
        template="core/controlframework/form.html", success_url="core:controlframework_list",
        extra_context={"notes": GRC_NOTES})


@require_POST
@tenant_admin_required
def controlframework_delete(request, pk):
    return crud_delete(request, model=ControlFramework, pk=pk,
                       success_url="core:controlframework_list")


@tenant_admin_required
def controlframeworkmapping_add(request, pk):
    """Map a control into this framework — the central operation of bullet 1.

    A GET form page rather than a POST-only verb, because choosing WHICH control to add is a
    selection and not a transition. The two refusals are the ones that matter: a `control_id` from
    another workspace is a 404 (never a 403 that would confirm the pk exists), and a control that
    is already mapped is a redirect with an informational message rather than an `IntegrityError`
    from the `unique_together` constraint.

    The new mapping starts at `coverage="not_started"` on purpose: nothing is covered the moment a
    row appears, and defaulting to a covered state would be the seeder's compliance-lie mistake in
    a different costume.
    """
    framework = get_object_or_404(ControlFramework, pk=pk, tenant=request.tenant)
    mapped_ids = framework.mappings.values_list("control_id", flat=True)
    if request.method == "POST":
        control_id = as_db_int(request.POST.get("control_id", ""))
        if control_id is None:
            messages.error(request, "Choose a control to add.")
            return redirect("core:controlframeworkmapping_add", pk=pk)
        # I12: `as_db_int`, not an `isdigit()` guard. `str.isdigit()` accepts `'²'` and an
        # unbounded 100-digit string, both of which convert/raise on the way into `int()` and
        # 500 with a DEBUG traceback -- and DEBUG defaults to True in config/settings.py, so the
        # traceback ships request.tenant and the queryset. The helper is the L11 rule this
        # comment previously and wrongly claimed was unnecessary. Tenant-scoped, so a foreign
        # pk is indistinguishable from a missing one.
        control = get_object_or_404(ComplianceControl, pk=control_id,
                                    tenant=request.tenant)
        mapping, created = ControlFrameworkMapping.objects.get_or_create(
            tenant=request.tenant, framework=framework, control=control,
            defaults={"coverage": "not_started"},
        )
        if created:
            write_audit_log(request.user, mapping, "create")
            messages.success(request, "Control mapping recorded. Coverage is not started yet — "
                                      "nothing is covered until somebody says so.")
        else:
            messages.info(request, "That control is already mapped to this framework.")
        return redirect("core:controlframework_detail", pk=pk)
    return render(request, "core/controlframeworkmapping/form.html", {
        "obj": framework,
        "framework": framework,
        "mapped_controls": framework.mappings.select_related("control"),
        # The picker is the tenant's own controls minus the ones already mapped, so the page
        # cannot offer a duplicate. Tenant-scoped for the same reason as the POST above.
        "available_controls": ComplianceControl.objects.filter(
            tenant=request.tenant).exclude(pk__in=mapped_ids).order_by("code"),
        "notes": GRC_NOTES,
    })



@tenant_admin_required
def controlframeworkmapping_list(request):
    qs = ControlFrameworkMapping.objects.filter(tenant=request.tenant).select_related(
        "framework", "control")
    return crud_list(
        request, qs, "core/controlframeworkmapping/list.html",
        search_fields=["framework__code", "control__code", "clause_reference"],
        filters=[("coverage", "coverage", False), ("framework", "framework_id", True)],
        extra_context={
            "coverage_choices": ControlFrameworkMapping.COVERAGE_CHOICES,
            # I4: `controls` is dropped. The list template's framework filter is populated from
            # `frameworks` only (verified by reading the template), so this queryset was dead
            # context. It cost zero queries -- an unevaluated queryset in a context is never
            # fetched -- so this is tidiness, not performance.
            "frameworks": ControlFramework.objects.filter(tenant=request.tenant),
            "notes": GRC_NOTES,
        },
    )


@tenant_admin_required
def controlframeworkmapping_create(request):
    return crud_create(
        request, form_class=ControlFrameworkMappingForm,
        template="core/controlframeworkmapping/form.html",
        success_url="core:controlframeworkmapping_list",
        extra_context={"notes": GRC_NOTES})


@require_POST
@tenant_admin_required
def controlframeworkmapping_delete(request, pk):
    return crud_delete(request, model=ControlFrameworkMapping, pk=pk,
                       success_url="core:controlframeworkmapping_list")


# ============================================================ bullet 1: the controls
@tenant_admin_required
def compliancecontrol_list(request):
    # C2/C3: the annotation is deliberately NOT named `framework_count`.
    # `ComplianceControl` has a `@property framework_count` (models/Compliance.py:338) and an
    # annotate() alias that collides with a property makes Django SET the attribute on the
    # instance, which raises `AttributeError: can't set attribute` and 500s this page
    # unconditionally. `mapping_total` is the same number under a name nothing else claims,
    # which also ends the three-way ambiguity I11 recorded: `framework_count` meant the
    # per-control mapping count here, the active-framework count on the board, and the
    # all-frameworks count on the framework list.
    qs = ComplianceControl.objects.filter(tenant=request.tenant).select_related("owner").annotate(
        mapping_total=Count("mappings", distinct=True)
    )
    # A GROUP BY suppresses `Meta.ordering` in Django, so without this the annotated list is
    # unordered: LIMIT/OFFSET pagination is then non-deterministic and it forfeits the
    # (tenant_id, code) unique index as its sort source. Order explicitly, by the same column.
    qs = qs.order_by("code")
    return crud_list(
        request, qs, "core/compliancecontrol/list.html",
        search_fields=["code", "title", "description", "category"],
        filters=[("status", "status", False)],
        extra_context={
            "status_choices": ComplianceControl.STATUS_CHOICES,
            "effective_count": qs.filter(status="effective").count(),
            # Counted in the DATABASE, not by walking the annotated queryset in Python. That
            # walk is what forced the GROUP BY evaluation at context-build time (C3), and it is
            # O(all controls) on every page load. `is_overdue_review` is
            # `next_review_on and next_review_on < today`; `__lt` excludes NULL for the same
            # reason, so a control with no review date is still not counted as overdue.
            "overdue_count": qs.filter(
                next_review_on__isnull=False,
                next_review_on__lt=timezone.localdate(),
            ).count(),
            # The gap figure: a control in no framework at all is a control no audit will ever ask
            # about, which is exactly what a framework register exists to surface. Reads the
            # renamed alias, since the property of the old name is shadowed by nothing now.
            "unmapped_count": qs.filter(mapping_total=0).count(),
            "notes": GRC_NOTES,
        },
    )


@tenant_admin_required
def compliancecontrol_create(request):
    return crud_create(
        request, form_class=ComplianceControlForm, template="core/compliancecontrol/form.html",
        success_url="core:compliancecontrol_list", extra_context={"notes": GRC_NOTES})


@tenant_admin_required
def compliancecontrol_detail(request, pk):
    control = get_object_or_404(ComplianceControl, pk=pk, tenant=request.tenant)
    return render(request, "core/compliancecontrol/detail.html", {
        "obj": control,
        "mappings": control.mappings.select_related("framework").order_by("framework__code"),
        "framework_count": control.mappings.count(),
        "notes": GRC_NOTES,
    })


@tenant_admin_required
def compliancecontrol_edit(request, pk):
    return crud_edit(
        request, model=ComplianceControl, pk=pk, form_class=ComplianceControlForm,
        template="core/compliancecontrol/form.html", success_url="core:compliancecontrol_list",
        extra_context={"notes": GRC_NOTES})


@require_POST
@tenant_admin_required
def compliancecontrol_delete(request, pk):
    return crud_delete(request, model=ComplianceControl, pk=pk,
                       success_url="core:compliancecontrol_list")



# ============================================================ bullet 2: policies
@tenant_admin_required
def corporatepolicy_list(request):
    # C2: NOT `acknowledged_count` -- `CorporatePolicy` has a `@property` of that name
    # (models/Compliance.py:492), and an annotate() alias colliding with a property makes
    # Django set the attribute on the instance and raise `AttributeError: can't set
    # attribute`. This page was the MASKED half of the same defect: because the crash only
    # happens once a row is actually instantiated, a filter matching nothing returned 200
    # with "No policies recorded" and nobody saw the 500. `acknowledgement_total` is the
    # same number under a name nothing else claims.
    qs = CorporatePolicy.objects.filter(tenant=request.tenant).select_related("owner").annotate(
        acknowledgement_total=Count("acknowledgements", distinct=True)
    )
    # GROUP BY suppresses Meta.ordering; order explicitly so LIMIT/OFFSET pagination is
    # deterministic and the (tenant_id, code) index can serve the sort.
    qs = qs.order_by("code")
    return crud_list(
        request, qs, "core/corporatepolicy/list.html",
        search_fields=["code", "title", "summary"],
        filters=[("status", "status", False), ("policy_type", "policy_type", False)],
        extra_context={
            "status_choices": CorporatePolicy.STATUS_CHOICES,
            "type_choices": CorporatePolicy.POLICY_TYPE_CHOICES,
            "published_count": qs.filter(status="published").count(),
            # I1: was `unacknowledged_count`, which said the opposite of what it counts --
            # it is the number of acknowledgements that EXIST against published policies.
            "acknowledgement_count": PolicyAcknowledgement.objects.filter(
                tenant=request.tenant, policy__status="published",
                policy__requires_acknowledgement=True).count(),
            "notes": GRC_NOTES,
        },
    )


@tenant_admin_required
def corporatepolicy_create(request):
    return crud_create(
        request, form_class=CorporatePolicyForm, template="core/corporatepolicy/form.html",
        success_url="core:corporatepolicy_list", extra_context={"notes": GRC_NOTES})


@tenant_admin_required
def corporatepolicy_detail(request, pk):
    policy = get_object_or_404(CorporatePolicy, pk=pk, tenant=request.tenant)
    return render(request, "core/corporatepolicy/detail.html", {
        "obj": policy,
        "acknowledgements": policy.acknowledgements.select_related("user"),
        # The rate is `None` (not 0) when it cannot be determined; the template prints an em dash.
        #
        # I9: `acknowledgement_rate`, `acknowledged_count` and
        # `superseded_acknowledgement_count` are all DB-hitting properties and a property is not
        # cached, so the template re-running each one per access meant the same COUNT was issued
        # two or three times for this one page. They are evaluated once here and handed to the
        # template as plain values; the template reads the names below, not `obj.<property>`.
        "acknowledgement_rate": policy.acknowledgement_rate,
        "acknowledged_count": policy.acknowledged_count,
        "superseded_acknowledgement_count": policy.superseded_acknowledgement_count,
        "notes": GRC_NOTES,
    })


@tenant_admin_required
def corporatepolicy_edit(request, pk):
    return crud_edit(
        request, model=CorporatePolicy, pk=pk, form_class=CorporatePolicyForm,
        template="core/corporatepolicy/form.html", success_url="core:corporatepolicy_list",
        extra_context={"notes": GRC_NOTES})


@require_POST
@tenant_admin_required
def corporatepolicy_delete(request, pk):
    """Delete a policy, but not the attestations recorded against it by accident.

    **I13 — a published policy carrying acknowledgements is evidence, not a draft.** Deleting it
    cascades its attestations away silently, and a direct POST bypasses the list page's JS
    `confirm()` entirely. So the delete is refused while attestations exist, and only an explicit
    `?discard_attestations=1` — which writes an audit row naming what was destroyed — gets past
    it. The refusal is the default because the recovery cost is asymmetric: a policy can be
    re-entered, an attestation cannot.
    """
    policy = get_object_or_404(CorporatePolicy, pk=pk, tenant=request.tenant)
    attributions = policy.acknowledgements.count()
    if attributions and request.POST.get("discard_attestations") != "1":
        messages.error(
            request,
            "This policy has %d acknowledgement%s recorded against it, and deleting it would "
            "destroy evidence somebody actually gave. Retire it instead, or re-send with "
            "discard_attestations=1 if you genuinely mean to destroy those records."
            % (attributions, "" if attributions == 1 else "s"),
        )
        return redirect("core:corporatepolicy_detail", pk=pk)
    if attributions:
        write_audit_log(
            request.user, policy, "delete",
            changes={"discarded_attestations": attributions},
        )
        policy.delete()
        messages.success(
            request,
            "Deleted, along with %d acknowledgement%s. The audit trail records that they were "
            "discarded." % (attributions, "" if attributions == 1 else "s"),
        )
        return redirect("core:corporatepolicy_list")
    return crud_delete(request, model=CorporatePolicy, pk=pk,
                       success_url="core:corporatepolicy_list")


@require_POST
@tenant_admin_required
def policy_acknowledge(request, pk):
    """Record that the SIGNED-IN user acknowledges this policy at its current version.

    **No form is bound**, deliberately. `PolicyAcknowledgementForm` has one optional field
    (`notes`) and acknowledging a policy without writing one is a legitimate act, so forcing a
    note would be inventing a requirement. Everything else on the row is evidence: the actor is
    `request.user`, the version is snapshotted from the policy, and the timestamp is `auto_now_add`.

    **The two refusals happen before anything is written.** A `draft` policy is not in force and a
    `retired` one is withdrawn — acknowledging either would put a row on the register that says
    somebody agreed to something that is not a policy any more. Neither writes an audit row.

    **`get_or_create` rather than `create`**, because the unique key is
    `(policy, user, policy_version)` and a double-click must be idempotent, not an `IntegrityError`
    on the second press.
    """
    policy = get_object_or_404(CorporatePolicy, pk=pk, tenant=request.tenant)
    if policy.status == "draft":
        messages.error(request, "This policy is still a draft — publish it before acknowledging.")
        return redirect("core:corporatepolicy_detail", pk=pk)
    if policy.status == "retired":
        messages.error(request, "This policy has been retired — there is nothing left to "
                                "acknowledge.")
        return redirect("core:corporatepolicy_detail", pk=pk)
    acknowledgement, created = PolicyAcknowledgement.objects.get_or_create(
        tenant=request.tenant,
        policy=policy,
        user=request.user,
        # The SNAPSHOT. Re-versioning the policy later must not rewrite what this row claims.
        policy_version=policy.version,
    )
    if created:
        write_audit_log(request.user, acknowledgement, "create")
        messages.success(request, "Acknowledgement recorded.")
    else:
        messages.info(request, "You have already acknowledged version %s of this policy."
                      % policy.version)
    return redirect("core:corporatepolicy_detail", pk=pk)



@tenant_admin_required
def policyacknowledgement_list(request):
    qs = PolicyAcknowledgement.objects.filter(tenant=request.tenant).select_related(
        "policy", "user")
    return crud_list(
        request, qs, "core/policyacknowledgement/list.html",
        search_fields=["policy__code", "user__username"],
        filters=[("policy", "policy_id", True)],
        extra_context={
            "policies": CorporatePolicy.objects.filter(tenant=request.tenant),
            "notes": GRC_NOTES,
        },
    )


def _acknowledgeable_users(tenant):
    """Active users of this tenant — the people a policy can be acknowledged by.

    Active only, and the same reason `CorporatePolicy.acknowledgement_rate` is `None` rather than
    `0`: a deactivated account is not somebody who failed to acknowledge.
    """
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(tenant=tenant, is_active=True).order_by("username")


@tenant_admin_required
def policyacknowledgement_create(request):
    """Back-fill an acknowledgement on somebody's behalf — the rare admin case.

    The normal path is `policy_acknowledge`, which stamps the actor from the session. This exists
    because an acknowledgement sometimes has to be recorded for somebody who is not at a keyboard,
    and it does NOT pretend otherwise: the view names the person in the success message and writes
    an audit row recording both who clicked and who it was for. `user` and `policy_version` are
    still never form fields — the template renders two plain pickers, not bound model fields, so a
    crafted POST still cannot forge a `policy_version` onto an existing row.
    """
    if request.method == "POST":
        form = PolicyAcknowledgementForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            # I12: `as_db_int` on both, not `str.isdigit()`. isdigit() returns True for '²' and
            # for a 100-digit string, and both then raise inside int() -- an uncaught 500 with a
            # DEBUG traceback (DEBUG defaults True here) exposing request.tenant and the queryset.
            policy_id = as_db_int(request.POST.get("policy", ""))
            user_id = as_db_int(request.POST.get("user", ""))
            if policy_id is None or user_id is None:
                messages.error(request, "Choose both a policy and a person.")
                return redirect("core:policyacknowledgement_create")
            # Both lookups are tenant-scoped, so a foreign pk is a 404, not a cross-tenant write.
            policy = get_object_or_404(CorporatePolicy, pk=policy_id,
                                       tenant=request.tenant)
            from django.contrib.auth import get_user_model
            person = get_object_or_404(get_user_model(), pk=user_id,
                                       tenant=request.tenant)
            # I2: the form's `notes` was bound and validated but never passed to get_or_create,
            # so a note typed into the back-fill form was silently discarded on the row it was
            # written to explain. `defaults` only applies on create, which is correct here: the
            # acknowledgement already exists, and overwriting its note on a duplicate submit
            # would rewrite evidence rather than record it.
            acknowledgement, created = PolicyAcknowledgement.objects.get_or_create(
                tenant=request.tenant, policy=policy, user=person,
                policy_version=policy.version,
                defaults={"notes": form.cleaned_data.get("notes") or ""},
            )
            if created:
                write_audit_log(request.user, acknowledgement, "create",
                                changes={"recorded_by": request.user.get_username(),
                                         "on_behalf_of": person.get_username(),
                                         "note": form.cleaned_data.get("notes") or ""})
                messages.success(request, "Acknowledgement recorded on behalf of %s."
                                 % person.get_username())
            else:
                messages.info(request, "That person has already acknowledged version %s."
                              % policy.version)
            return redirect("core:policyacknowledgement_list")
    else:
        form = PolicyAcknowledgementForm(tenant=request.tenant)
    return render(request, "core/policyacknowledgement/form.html", {
        "form": form,
        "is_edit": False,
        "policies": CorporatePolicy.objects.filter(tenant=request.tenant),
        "people": _acknowledgeable_users(request.tenant),
        "notes": GRC_NOTES,
    })


@require_POST
@tenant_admin_required
def policyacknowledgement_delete(request, pk):
    """I13 — an acknowledgement is EVIDENCE, and evidence is not deleted from a register.

    Every other 0.21 entity is a working register an admin is entitled to correct. This one is
    different: the row asserts that a named person pressed a button at a timestamp, and the only
    honest corrections are "this was recorded for the wrong person" (which the back-fill view
    already flags in the audit trail) and "this person has since been removed" (which
    `acknowledgement_rate` handles by counting only active users). Deleting the row would leave
    no trace that the attestation ever existed, so this refuses outright rather than merely
    warning: an admin who can delete an attestation can also quietly manufacture a clean register.
    """
    acknowledgement = get_object_or_404(PolicyAcknowledgement, pk=pk,
                                       tenant=request.tenant)
    messages.error(
        request,
        "An acknowledgement cannot be deleted - it is a record that %s pressed save on %s v%s. "
        "The audit trail for this entry is the permanent record of it."
        % (acknowledgement.user.get_username(),
           acknowledgement.policy.code, acknowledgement.policy_version),
    )
    return redirect("core:policyacknowledgement_list")



# ============================================================ bullet 3: the risk register
@tenant_admin_required
def riskregister_list(request):
    # I7: select_related("owner"), matching riskregister_detail. Without it the list template's
    # Owner column is one extra query per row.
    qs = RiskRegister.objects.filter(tenant=request.tenant).select_related("owner")
    return crud_list(
        request, qs, "core/riskregister/list.html",
        search_fields=["code", "title", "risk_statement", "category"],
        filters=[("status", "status", False), ("treatment", "treatment", False),
                 ("likelihood", "likelihood", False)],
        extra_context={
            "status_choices": RiskRegister.STATUS_CHOICES,
            "treatment_choices": RiskRegister.TREATMENT_CHOICES,
            "likelihood_choices": RiskRegister.LIKELIHOOD_CHOICES,
            "open_count": qs.filter(status__in=RiskRegister.OPEN_STATUSES).count(),
            # The band, counted in SQL. `score_label` is `inherent_score > 16` for "critical"
            # (models/Compliance.py:668-674) -- the same boundary, read off the stored score
            # rather than re-derived by walking every row in Python (I8).
            "critical_count": qs.filter(inherent_score__gt=16).count(),
            "notes": GRC_NOTES,
        },
    )


@tenant_admin_required
def riskregister_create(request):
    return crud_create(
        request, form_class=RiskRegisterForm, template="core/riskregister/form.html",
        success_url="core:riskregister_list", extra_context={"notes": GRC_NOTES})


@tenant_admin_required
def riskregister_detail(request, pk):
    return crud_detail(
        request, model=RiskRegister, pk=pk, template="core/riskregister/detail.html",
        select_related=("owner",),
        extra_context={"notes": GRC_NOTES},
    )


@tenant_admin_required
def riskregister_edit(request, pk):
    return crud_edit(
        request, model=RiskRegister, pk=pk, form_class=RiskRegisterForm,
        template="core/riskregister/form.html", success_url="core:riskregister_list",
        extra_context={"notes": GRC_NOTES})


@require_POST
@tenant_admin_required
def riskregister_delete(request, pk):
    return crud_delete(request, model=RiskRegister, pk=pk, success_url="core:riskregister_list")


# ============================================================ the board
@tenant_admin_required
def grc_overview(request):
    """COMPUTED hub for 0.21 — no table of its own, and no figure it cannot measure.

    A tenant-less user (the superuser) is redirected with an explanation rather than shown a board
    full of zeros: the zero rule taken one step further, where a whole page of `0`s about nobody's
    workspace is worse than no page.
    """
    if request.tenant is None:
        messages.info(request, "Compliance posture applies to a tenant workspace.")
        return redirect("dashboard:home")
    tenant = request.tenant
    controls = ComplianceControl.objects.filter(tenant=tenant)
    risks = RiskRegister.objects.filter(tenant=tenant)
    policies = CorporatePolicy.objects.filter(tenant=tenant)
    # I8: every figure below is a DB-side COUNT. The three `sum(1 for ...)` aggregates walked
    # whole querysets in Python on every board load, which is O(all rows) to produce one integer.
    # `score_label` is `> 16` for "critical" (models/Compliance.py:668-674), so the band is
    # reproduced as a filter on the stored score rather than by re-deriving it in Python.
    # `is_overdue_review` is `next_review_on and next_review_on < today`; `__lt` excludes NULL
    # for the same reason, so a row with no review date is still not counted overdue.
    today = timezone.localdate()
    return render(request, "core/grcoverview.html", {
        "frameworks": ControlFramework.objects.filter(tenant=tenant, is_active=True)[:8],
        "framework_count": ControlFramework.objects.filter(tenant=tenant).count(),
        "control_count": controls.count(),
        "effective_count": controls.filter(status="effective").count(),
        "published_policies": policies.filter(status="published").count(),
        "risks": risks[:8],
        "open_risks": risks.filter(status__in=RiskRegister.OPEN_STATUSES).count(),
        "critical_risks": risks.filter(inherent_score__gt=16).count(),
        "overdue_reviews": (
            controls.filter(next_review_on__lt=today).count()
            + risks.filter(next_review_on__lt=today).count()
        ),
        "notes": GRC_NOTES,
    })
