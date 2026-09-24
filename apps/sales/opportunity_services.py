from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import Tenant
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.models.OpportunityPipeline.Pipelines import (
    PIPELINE_CRITERION_CHOICES,
    OpportunityPipelinePlacement,
    Pipeline,
    PipelineStage,
)
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import (
    CompetitorProfile,
    OpportunityCompetitor,
)
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import (
    OpportunityOutcome,
    WinLossReason,
)
from apps.sales.models.OpportunityTeams.OpportunityTeams import OpportunityTeamMember


def _opportunity_pipeline_tenant_id(tenant):
    return getattr(tenant, "pk", tenant)


def _opportunity_pipeline_lock_tenant(tenant):
    Tenant.objects.select_for_update().get(pk=_opportunity_pipeline_tenant_id(tenant))


def opportunity_pipeline_baseline_stages():
    labels = dict(PIPELINE_CRITERION_CHOICES)
    return [
        {
            "name": "Prospecting",
            "code": "prospecting",
            "sequence": 10,
            "stage_kind": "open",
            "crm_stage_key": "prospecting",
            "probability": 10,
            "forecast_category": "pipeline",
            "entry_criteria": [],
            "exit_criteria": [
                {"key": "account", "label": labels["account"]},
                {"key": "primary_contact", "label": labels["primary_contact"]},
            ],
            "target_days": 14,
            "is_active": True,
        },
        {
            "name": "Discovery / Qualification",
            "code": "qualification",
            "sequence": 20,
            "stage_kind": "open",
            "crm_stage_key": "qualification",
            "probability": 30,
            "forecast_category": "pipeline",
            "entry_criteria": [],
            "exit_criteria": [
                {"key": "amount", "label": labels["amount"]},
                {"key": "close_date", "label": labels["close_date"]},
            ],
            "target_days": 21,
            "is_active": True,
        },
        {
            "name": "Proposal",
            "code": "proposal",
            "sequence": 30,
            "stage_kind": "open",
            "crm_stage_key": "proposal",
            "probability": 60,
            "forecast_category": "best_case",
            "entry_criteria": [],
            "exit_criteria": [
                {"key": "next_step", "label": labels["next_step"]},
                {"key": "next_step_due_date", "label": labels["next_step_due_date"]},
            ],
            "target_days": 21,
            "is_active": True,
        },
        {
            "name": "Negotiation",
            "code": "negotiation",
            "sequence": 40,
            "stage_kind": "open",
            "crm_stage_key": "negotiation",
            "probability": 80,
            "forecast_category": "commit",
            "entry_criteria": [],
            "exit_criteria": [],
            "target_days": 14,
            "is_active": True,
        },
        {
            "name": "Closed Won",
            "code": "closed_won",
            "sequence": 50,
            "stage_kind": "won",
            "crm_stage_key": "closed_won",
            "probability": 100,
            "forecast_category": "closed",
            "entry_criteria": [],
            "exit_criteria": [],
            "target_days": None,
            "is_active": True,
        },
        {
            "name": "Closed Lost",
            "code": "closed_lost",
            "sequence": 60,
            "stage_kind": "lost",
            "crm_stage_key": "closed_lost",
            "probability": 0,
            "forecast_category": "closed",
            "entry_criteria": [],
            "exit_criteria": [],
            "target_days": None,
            "is_active": True,
        },
    ]


def _opportunity_pipeline_create_baseline_stages(pipeline):
    stages = [
        PipelineStage(tenant=pipeline.tenant, pipeline=pipeline, **values)
        for values in opportunity_pipeline_baseline_stages()
    ]
    PipelineStage.objects.bulk_create(stages)
    return stages


def _opportunity_pipeline_validate_active_shape(pipeline, exclude_stage_id=None):
    active_stages = PipelineStage.objects.filter(
        tenant=pipeline.tenant,
        pipeline=pipeline,
        is_active=True,
    )
    if exclude_stage_id is not None:
        active_stages = active_stages.exclude(pk=exclude_stage_id)
    open_count = active_stages.filter(stage_kind="open").count()
    won_count = active_stages.filter(stage_kind="won").count()
    lost_count = active_stages.filter(stage_kind="lost").count()
    if open_count < 1 or won_count != 1 or lost_count != 1:
        raise ValidationError(
            "An active pipeline needs at least one open stage, exactly one won stage, and exactly one lost stage."
        )


def _opportunity_pipeline_clear_default(tenant, pipeline):
    now = timezone.now()
    previous_defaults = list(
        Pipeline.objects.select_for_update()
        .filter(tenant=tenant, is_active=True, is_default=True)
        .exclude(pk=pipeline.pk)
    )
    if previous_defaults:
        Pipeline.objects.filter(pk__in=[row.pk for row in previous_defaults]).update(
            is_default=False,
            updated_at=now,
        )
    return previous_defaults


def sales_create_pipeline(tenant, validated_data, user):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    if tenant_id is None:
        raise ValidationError("A tenant workspace is required.")
    values = dict(validated_data)
    desired_active = bool(values.pop("is_active", True))
    desired_default = bool(values.pop("is_default", False))
    if desired_default and not desired_active:
        raise ValidationError("The default pipeline must be active.")
    with transaction.atomic():
        _opportunity_pipeline_lock_tenant(tenant)
        pipeline = Pipeline(
            tenant=tenant,
            is_active=False,
            is_default=False,
            **values,
        )
        pipeline.full_clean()
        pipeline.save()
        _opportunity_pipeline_create_baseline_stages(pipeline)
        if desired_active:
            _opportunity_pipeline_validate_active_shape(pipeline)
        if desired_default:
            _opportunity_pipeline_clear_default(tenant, pipeline)
        pipeline.is_active = desired_active
        pipeline.is_default = desired_default
        pipeline.full_clean()
        pipeline.save()
        write_audit_log(
            user,
            pipeline,
            "create",
            {"operation": "create_pipeline"},
            tenant=tenant,
        )
    return pipeline


def sales_set_default_pipeline(pipeline, tenant, user):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    if pipeline.tenant_id != tenant_id:
        raise ValidationError("The pipeline must belong to this workspace.")
    with transaction.atomic():
        _opportunity_pipeline_lock_tenant(tenant)
        locked = Pipeline.objects.select_for_update().get(pk=pipeline.pk, tenant=tenant)
        if not locked.is_active:
            raise ValidationError("Only an active pipeline can be the default.")
        if locked.is_default:
            return locked
        _opportunity_pipeline_clear_default(tenant, locked)
        locked.is_default = True
        locked.full_clean()
        locked.save(update_fields=["is_default", "updated_at"])
        write_audit_log(
            user,
            locked,
            "update",
            {"operation": "set_default_pipeline"},
            tenant=tenant,
        )
    return locked


def sales_save_pipeline(pipeline, tenant, user, validated_data):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    if pipeline.tenant_id != tenant_id:
        raise ValidationError("The pipeline must belong to this workspace.")
    with transaction.atomic():
        _opportunity_pipeline_lock_tenant(tenant)
        locked = Pipeline.objects.select_for_update().get(pk=pipeline.pk, tenant=tenant)
        values = dict(validated_data)
        desired_active = bool(values.get("is_active", locked.is_active))
        desired_default = bool(values.get("is_default", locked.is_default))
        if desired_default and not desired_active:
            raise ValidationError("The default pipeline must be active.")
        if desired_active and not PipelineStage.objects.filter(pipeline=locked).exists():
            _opportunity_pipeline_create_baseline_stages(locked)
        if desired_active:
            _opportunity_pipeline_validate_active_shape(locked)
        if desired_default:
            _opportunity_pipeline_clear_default(tenant, locked)
        for field_name, value in values.items():
            setattr(locked, field_name, value)
        locked.full_clean()
        locked.save()
        write_audit_log(
            user,
            locked,
            "update",
            {"operation": "update_pipeline"},
            tenant=tenant,
        )
    return locked


def sales_save_pipeline_stage(stage, tenant, user, validated_data, pipeline=None):
    values = dict(validated_data)
    bound_pipeline_id = getattr(pipeline, "pk", None)
    submitted_pipeline = values.get("pipeline")
    if bound_pipeline_id is not None and submitted_pipeline is not None:
        if submitted_pipeline.pk != bound_pipeline_id:
            raise ValidationError("A pipeline stage cannot move to another pipeline.")
    pipeline_id = bound_pipeline_id or getattr(submitted_pipeline, "pk", None) or getattr(stage, "pipeline_id", None)
    if pipeline_id is None:
        raise ValidationError("Choose a pipeline for this stage.")
    with transaction.atomic():
        locked_pipeline = Pipeline.objects.select_for_update().get(pk=pipeline_id, tenant=tenant)
        if stage.pk:
            locked_stage = PipelineStage.objects.select_for_update().get(
                pk=stage.pk,
                tenant=tenant,
                pipeline=locked_pipeline,
            )
            submitted_pipeline = values.get("pipeline")
            if submitted_pipeline and submitted_pipeline.pk != locked_pipeline.pk:
                raise ValidationError("A pipeline stage cannot move to another pipeline.")
        else:
            locked_stage = PipelineStage(tenant=tenant, pipeline=locked_pipeline)
        for field_name, value in values.items():
            setattr(locked_stage, field_name, value)
        locked_stage.pipeline = locked_pipeline
        sequence = locked_stage.sequence
        if PipelineStage.objects.filter(
            tenant=tenant,
            pipeline=locked_pipeline,
            sequence=sequence,
        ).exclude(pk=locked_stage.pk).exists():
            raise ValidationError({"sequence": "That stage sequence is already in use."})
        locked_stage.full_clean()
        locked_stage.save()
        if locked_pipeline.is_active:
            _opportunity_pipeline_validate_active_shape(locked_pipeline)
        write_audit_log(
            user,
            locked_stage,
            "create" if not stage.pk else "update",
            {"operation": "create_pipeline_stage" if not stage.pk else "update_pipeline_stage"},
            tenant=tenant,
        )
    return locked_stage


def sales_delete_pipeline_stage(stage, tenant, user):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    if stage.tenant_id != tenant_id:
        raise ValidationError("The pipeline stage must belong to this workspace.")
    with transaction.atomic():
        locked_pipeline = Pipeline.objects.select_for_update().get(
            pk=stage.pipeline_id,
            tenant=tenant,
        )
        locked_stage = PipelineStage.objects.select_for_update().get(
            pk=stage.pk,
            pipeline=locked_pipeline,
            tenant=tenant,
        )
        if locked_stage.current_placements.exists():
            raise ValidationError("A stage used by a placement cannot be deleted.")
        if locked_pipeline.is_active:
            _opportunity_pipeline_validate_active_shape(
                locked_pipeline,
                exclude_stage_id=locked_stage.pk,
            )
        write_audit_log(
            user,
            locked_stage,
            "delete",
            {"operation": "delete_pipeline_stage"},
            tenant=tenant,
        )
        locked_stage.delete()
    return True


def sales_reorder_pipeline_stages(pipeline, tenant, user, ordered_stage_ids):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    if pipeline.tenant_id != tenant_id:
        raise ValidationError("The pipeline must belong to this workspace.")
    if isinstance(ordered_stage_ids, str):
        tokens = [token for token in ordered_stage_ids.replace(",", " ").split() if token]
        if not tokens or any(not token.isdigit() for token in tokens):
            raise ValidationError("The reorder must contain every pipeline stage exactly once.")
        ordered_stage_ids = [int(token) for token in tokens]
    ordered_stage_ids = [int(stage_id) for stage_id in ordered_stage_ids]
    with transaction.atomic():
        locked_pipeline = Pipeline.objects.select_for_update().get(pk=pipeline.pk, tenant=tenant)
        locked_stages = list(
            PipelineStage.objects.select_for_update()
            .filter(tenant=tenant, pipeline=locked_pipeline)
            .order_by("sequence", "pk")
        )
        current_ids = [stage.pk for stage in locked_stages]
        if len(ordered_stage_ids) != len(current_ids) or set(ordered_stage_ids) != set(current_ids):
            raise ValidationError("The reorder must contain every pipeline stage exactly once.")
        if ordered_stage_ids == current_ids:
            return locked_pipeline
        temporary_start = max((stage.sequence for stage in locked_stages), default=0) + len(locked_stages) + 1
        final_sequences = [(index + 1) * 10 for index in range(len(ordered_stage_ids))]
        if temporary_start + len(locked_stages) - 1 > 2147483647 or final_sequences[-1] > 2147483647:
            raise ValidationError("Stage sequences cannot be reordered within database limits.")
        now = timezone.now()
        stage_by_id = {stage.pk: stage for stage in locked_stages}
        for offset, stage_id in enumerate(ordered_stage_ids):
            PipelineStage.objects.filter(pk=stage_id, tenant=tenant, pipeline=locked_pipeline).update(
                sequence=temporary_start + offset,
                updated_at=now,
            )
            stage_by_id[stage_id].sequence = temporary_start + offset
        for sequence, stage_id in enumerate(final_sequences):
            PipelineStage.objects.filter(pk=stage_id, tenant=tenant, pipeline=locked_pipeline).update(
                sequence=sequence,
                updated_at=now,
            )
            stage_by_id[stage_id].sequence = sequence
        write_audit_log(
            user,
            locked_pipeline,
            "update",
            {"operation": "reorder_pipeline_stages", "stage_ids": ordered_stage_ids},
            tenant=tenant,
        )
    return locked_pipeline


def sales_validate_stage_criteria(
    stage,
    opportunity,
    active_team_member=False,
    criteria=None,
    criterion_name="entry",
):
    next_step_due_date = getattr(opportunity, "next_step_due_date", None)
    checks = {
        "account": opportunity.account_id is not None,
        "primary_contact": opportunity.primary_contact_id is not None,
        "amount": Decimal(opportunity.amount or 0) > 0,
        "close_date": opportunity.close_date is not None,
        "next_step": bool((opportunity.next_step or "").strip()),
        "next_step_due_date": next_step_due_date is not None,
        "owner": opportunity.owner_id is not None,
        "active_team_member": bool(active_team_member),
    }
    criteria = stage.entry_criteria if criteria is None else criteria
    if not isinstance(criteria, (list, tuple)) or len(criteria) > 20:
        raise ValidationError("Stage criteria are invalid.")
    missing = []
    for item in criteria:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if key not in checks or checks[key]:
            continue
        missing.append(str(item.get("label") or key))
    if missing:
        raise ValidationError(
            f"Stage {criterion_name} criteria are not met: " + ", ".join(missing)
        )
    return True


def _opportunity_pipeline_effective_probability(stage, probability_override):
    if probability_override is None:
        return stage.probability
    if isinstance(probability_override, bool) or not isinstance(probability_override, int):
        raise ValidationError("Probability override must be an integer from 0 to 100.")
    if not 0 <= probability_override <= 100:
        raise ValidationError("Probability override must be an integer from 0 to 100.")
    if stage.stage_kind == "won" and probability_override != 100:
        raise ValidationError("Won placements require a 100% probability override.")
    if stage.stage_kind == "lost" and probability_override != 0:
        raise ValidationError("Lost placements require a 0% probability override.")
    return probability_override


def sales_place_opportunity(
    opportunity,
    pipeline,
    stage,
    tenant,
    user,
    probability_override=None,
    active_team_member=False,
):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    if opportunity.tenant_id != tenant_id:
        raise ValidationError("The opportunity must belong to this workspace.")
    with transaction.atomic():
        locked_opportunity = Opportunity.objects.select_for_update().get(
            pk=opportunity.pk,
            tenant=tenant,
        )
        locked_pipeline = Pipeline.objects.select_for_update().get(pk=pipeline.pk, tenant=tenant)
        locked_stage = PipelineStage.objects.select_for_update().get(pk=stage.pk, tenant=tenant)
        if not locked_pipeline.is_active:
            raise ValidationError("Choose an active pipeline.")
        if not locked_stage.is_active or locked_stage.pipeline_id != locked_pipeline.pk:
            raise ValidationError("Choose an active stage from the selected pipeline.")
        effective_probability = _opportunity_pipeline_effective_probability(
            locked_stage,
            probability_override,
        )
        sales_validate_stage_criteria(
            locked_stage,
            locked_opportunity,
            active_team_member=active_team_member,
        )
        locked_placement = (
            OpportunityPipelinePlacement.objects.select_for_update()
            .filter(tenant=tenant, opportunity=locked_opportunity)
            .first()
        )
        if (
            locked_placement is not None
            and locked_placement.pipeline_id == locked_pipeline.pk
            and locked_placement.current_stage_id == locked_stage.pk
            and locked_placement.probability_override == probability_override
        ):
            return locked_placement
        now = timezone.now()
        created = locked_placement is None
        stage_changed = (
            created
            or locked_placement.pipeline_id != locked_pipeline.pk
            or locked_placement.current_stage_id != locked_stage.pk
        )
        if created:
            locked_placement = OpportunityPipelinePlacement(
                tenant=tenant,
                opportunity=locked_opportunity,
            )
        locked_placement.pipeline = locked_pipeline
        locked_placement.current_stage = locked_stage
        locked_placement.probability_override = probability_override
        if stage_changed:
            locked_placement.stage_entered_at = now
        locked_placement.full_clean()
        locked_placement.save()
        locked_opportunity.stage = locked_stage.crm_stage_key
        locked_opportunity.probability = effective_probability
        locked_opportunity.forecast_category = locked_stage.forecast_category
        locked_opportunity.save()
        write_audit_log(
            user,
            locked_placement,
            "create" if created else "update",
            {
                "operation": "place",
                "pipeline_id": locked_pipeline.pk,
                "stage_id": locked_stage.pk,
                "effective_probability": effective_probability,
            },
            tenant=tenant,
        )
    return locked_placement


def sales_unplace_opportunity(opportunity, tenant, user):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    if opportunity.tenant_id != tenant_id:
        raise ValidationError("The opportunity must belong to this workspace.")
    with transaction.atomic():
        Opportunity.objects.select_for_update().get(pk=opportunity.pk, tenant=tenant)
        placement = (
            OpportunityPipelinePlacement.objects.select_for_update()
            .filter(tenant=tenant, opportunity=opportunity)
            .first()
        )
        if placement is None:
            return False
        write_audit_log(
            user,
            placement,
            "delete",
            {"operation": "unplace"},
            tenant=tenant,
        )
        placement.delete()
    return True


def sales_save_opportunity_competitor(opportunity, competitor, tenant, user, validated_data):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    if opportunity.tenant_id != tenant_id:
        raise ValidationError("The opportunity must belong to this workspace.")
    values = dict(validated_data or {})
    with transaction.atomic():
        locked_opportunity = Opportunity.objects.select_for_update().get(
            pk=opportunity.pk,
            tenant=tenant,
        )
        competitor_id = getattr(competitor, "pk", competitor)
        if competitor_id:
            locked_competitor = (
                OpportunityCompetitor.objects.select_for_update()
                .filter(
                    pk=competitor_id,
                    tenant=tenant,
                    opportunity=locked_opportunity,
                )
                .first()
            )
            if locked_competitor is None:
                raise ValidationError("The competitor link does not belong to this opportunity.")
            created = False
        else:
            if competitor is not None and getattr(competitor, "opportunity_id", None) not in (
                None,
                locked_opportunity.pk,
            ):
                raise ValidationError("The competitor link does not belong to this opportunity.")
            locked_competitor = OpportunityCompetitor(
                tenant=tenant,
                opportunity=locked_opportunity,
            )
            created = True
        profile = values.get("competitor_profile")
        profile_id = getattr(profile, "pk", profile)
        if not profile_id:
            raise ValidationError({"competitor_profile": "Choose a competitor profile."})
        locked_profile = (
            CompetitorProfile.objects.select_for_update()
            .filter(pk=profile_id, tenant=tenant)
            .first()
        )
        if locked_profile is None:
            raise ValidationError({"competitor_profile": "Choose a competitor profile from this workspace."})
        if not locked_profile.is_active and locked_competitor.competitor_profile_id != locked_profile.pk:
            raise ValidationError({"competitor_profile": "Choose an active competitor profile."})
        locked_competitor.tenant = tenant
        locked_competitor.opportunity = locked_opportunity
        locked_competitor.competitor_profile = locked_profile
        for field_name in (
            "relationship",
            "is_primary",
            "pricing_notes",
            "deal_notes",
            "positioning_notes",
        ):
            if field_name in values:
                setattr(locked_competitor, field_name, values[field_name])
        if "is_primary" in values and not isinstance(values["is_primary"], bool):
            raise ValidationError({"is_primary": "Choose a valid primary setting."})
        locked_competitor.full_clean()
        cleared_primary_ids = []
        if locked_competitor.is_primary:
            other_links = OpportunityCompetitor.objects.select_for_update().filter(
                tenant=tenant,
                opportunity=locked_opportunity,
                is_primary=True,
            )
            if locked_competitor.pk:
                other_links = other_links.exclude(pk=locked_competitor.pk)
            cleared_primary_ids = list(other_links.values_list("pk", flat=True))
            if cleared_primary_ids:
                OpportunityCompetitor.objects.filter(pk__in=cleared_primary_ids).update(
                    is_primary=False,
                    updated_at=timezone.now(),
                )
        locked_competitor.save()
        write_audit_log(
            user,
            locked_competitor,
            "create" if created else "update",
            {
                "operation": "add_competitor" if created else "update_competitor",
                "link_id": locked_competitor.pk,
                "opportunity_id": locked_opportunity.pk,
                "competitor_profile_id": locked_profile.pk,
                "relationship": locked_competitor.relationship,
                "is_primary": locked_competitor.is_primary,
                "cleared_primary_ids": cleared_primary_ids,
            },
            tenant=tenant,
        )
    return locked_competitor


def sales_remove_opportunity_competitor(opportunity, competitor, tenant, user):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    if opportunity.tenant_id != tenant_id:
        raise ValidationError("The opportunity must belong to this workspace.")
    competitor_id = getattr(competitor, "pk", competitor)
    if not competitor_id:
        raise ValidationError("The competitor link does not belong to this opportunity.")
    with transaction.atomic():
        locked_opportunity = Opportunity.objects.select_for_update().get(
            pk=opportunity.pk,
            tenant=tenant,
        )
        locked_competitor = (
            OpportunityCompetitor.objects.select_for_update()
            .filter(
                pk=competitor_id,
                tenant=tenant,
                opportunity=locked_opportunity,
            )
            .first()
        )
        if locked_competitor is None:
            raise ValidationError("The competitor link does not belong to this opportunity.")
        write_audit_log(
            user,
            locked_competitor,
            "delete",
            {
                "operation": "remove_competitor",
                "link_id": locked_competitor.pk,
                "opportunity_id": locked_opportunity.pk,
                "competitor_profile_id": locked_competitor.competitor_profile_id,
            },
            tenant=tenant,
        )
        locked_competitor.delete()
    return True


def _opportunity_transition_pk(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if 0 < parsed <= 9223372036854775807 else None


def _opportunity_transition_lock_stage(stage_id, tenant_id, pipeline_id=None):
    queryset = PipelineStage.objects.select_for_update().filter(
        pk=stage_id,
        tenant_id=tenant_id,
    )
    if pipeline_id is not None:
        queryset = queryset.filter(pipeline_id=pipeline_id)
    try:
        return queryset.get()
    except PipelineStage.DoesNotExist as exc:
        raise ValidationError("The stage does not belong to this workspace.") from exc


def _opportunity_transition_lock_reason(reason_id, tenant_id):
    try:
        return WinLossReason.objects.select_for_update().get(
            pk=reason_id,
            tenant_id=tenant_id,
        )
    except WinLossReason.DoesNotExist as exc:
        raise ValidationError("The win/loss reason does not belong to this workspace.") from exc


def _opportunity_transition_lock_competitor(competitor_id, tenant_id, opportunity_id):
    try:
        return OpportunityCompetitor.objects.select_for_update().get(
            pk=competitor_id,
            tenant_id=tenant_id,
            opportunity_id=opportunity_id,
        )
    except OpportunityCompetitor.DoesNotExist as exc:
        raise ValidationError("The competitor link does not belong to this opportunity.") from exc


def _opportunity_transition_validate_stage_projection(stage):
    expected = {
        "won": ("closed_won", 100, "closed"),
        "lost": ("closed_lost", 0, "closed"),
    }.get(stage.stage_kind)
    if expected is not None and (
        stage.crm_stage_key,
        stage.probability,
        stage.forecast_category,
    ) != expected:
        raise ValidationError("Closed stage projection values are invalid.")


def sales_transition_opportunity(
    *,
    opportunity,
    target_stage,
    tenant,
    user,
    reason=None,
    competitor_link=None,
    notes="",
):
    tenant_id = _opportunity_pipeline_tenant_id(tenant)
    opportunity_id = _opportunity_transition_pk(getattr(opportunity, "pk", opportunity))
    target_stage_id = _opportunity_transition_pk(getattr(target_stage, "pk", target_stage))
    if tenant_id is None or opportunity_id is None or target_stage_id is None:
        raise ValidationError("A tenant, opportunity, and target stage are required.")
    if opportunity.tenant_id != tenant_id:
        raise ValidationError("The opportunity must belong to this workspace.")
    if notes is None:
        notes = ""
    if not isinstance(notes, str) or len(notes) > 4000:
        raise ValidationError("Transition notes must be text of at most 4000 characters.")
    notes = notes.strip()
    if user is not None and getattr(user, "is_authenticated", False):
        if getattr(user, "tenant_id", None) != tenant_id:
            raise ValidationError("The user must belong to this workspace.")
    reason_id = _opportunity_transition_pk(getattr(reason, "pk", reason))
    competitor_id = _opportunity_transition_pk(getattr(competitor_link, "pk", competitor_link))
    with transaction.atomic():
        try:
            locked_opportunity = Opportunity.objects.select_for_update().get(
                pk=opportunity_id,
                tenant_id=tenant_id,
            )
        except Opportunity.DoesNotExist as exc:
            raise ValidationError("The opportunity does not belong to this workspace.") from exc
        try:
            locked_placement = OpportunityPipelinePlacement.objects.select_for_update().get(
                opportunity_id=locked_opportunity.pk,
                tenant_id=tenant_id,
            )
        except OpportunityPipelinePlacement.DoesNotExist as exc:
            raise ValidationError("Place this opportunity in a pipeline before transitioning it.") from exc
        try:
            locked_pipeline = Pipeline.objects.select_for_update().get(
                pk=locked_placement.pipeline_id,
                tenant_id=tenant_id,
            )
        except Pipeline.DoesNotExist as exc:
            raise ValidationError("The placement pipeline does not belong to this workspace.") from exc
        locked_current = _opportunity_transition_lock_stage(
            locked_placement.current_stage_id,
            tenant_id,
            locked_placement.pipeline_id,
        )
        locked_target = _opportunity_transition_lock_stage(
            target_stage_id,
            tenant_id,
            locked_placement.pipeline_id,
        )
        if not locked_pipeline.is_active:
            raise ValidationError("The placement pipeline must be active.")
        if not locked_current.is_active or not locked_target.is_active:
            raise ValidationError("The current and target stages must be active.")
        _opportunity_transition_validate_stage_projection(locked_current)
        _opportunity_transition_validate_stage_projection(locked_target)
        if locked_current.pipeline_id != locked_placement.pipeline_id or locked_target.pipeline_id != locked_placement.pipeline_id:
            raise ValidationError("The current and target stages must belong to the placement pipeline.")
        if locked_current.pk == locked_target.pk:
            return locked_placement
        if locked_current.stage_kind == "open":
            if locked_target.stage_kind == "open":
                if locked_target.sequence <= locked_current.sequence:
                    raise ValidationError("An open opportunity cannot move backward between stages.")
                next_open_id = (
                    PipelineStage.objects.filter(
                        tenant_id=tenant_id,
                        pipeline_id=locked_placement.pipeline_id,
                        is_active=True,
                        stage_kind="open",
                        sequence__gt=locked_current.sequence,
                    )
                    .order_by("sequence", "pk")
                    .values_list("pk", flat=True)
                    .first()
                )
                if next_open_id != locked_target.pk:
                    raise ValidationError("An open opportunity must move to the next active open stage.")
            elif locked_target.stage_kind not in {"won", "lost"}:
                raise ValidationError("That pipeline transition is not available.")
        elif locked_current.stage_kind in {"won", "lost"}:
            if locked_target.stage_kind != "open":
                raise ValidationError("A closed opportunity can only reopen to an open stage.")
        else:
            raise ValidationError("The current pipeline stage is invalid.")
        active_team_member = (
            OpportunityTeamMember.objects.select_for_update()
            .filter(
                tenant_id=tenant_id,
                opportunity_id=locked_opportunity.pk,
                is_active=True,
            )
            .exists()
        )
        sales_validate_stage_criteria(
            locked_current,
            locked_opportunity,
            active_team_member=active_team_member,
            criteria=locked_current.exit_criteria,
            criterion_name="exit",
        )
        sales_validate_stage_criteria(
            locked_target,
            locked_opportunity,
            active_team_member=active_team_member,
            criteria=locked_target.entry_criteria,
            criterion_name="entry",
        )
        locked_reason = _opportunity_transition_lock_reason(reason_id, tenant_id) if reason_id else None
        locked_competitor = (
            _opportunity_transition_lock_competitor(
                competitor_id,
                tenant_id,
                locked_opportunity.pk,
            )
            if competitor_id
            else None
        )
        if locked_target.stage_kind == "open":
            if locked_reason is not None or locked_competitor is not None:
                raise ValidationError("Open transitions cannot carry closure evidence.")
        else:
            if locked_reason is None:
                raise ValidationError("A reason is required when closing an opportunity.")
            if not locked_reason.is_active:
                raise ValidationError("Choose an active win/loss reason.")
            if locked_reason.result not in {"both", locked_target.stage_kind}:
                raise ValidationError("The reason is not compatible with the closing result.")
            if (
                locked_competitor is not None
                and locked_competitor.relationship in {"lost_to", "beaten"}
                and locked_target.stage_kind != "lost"
            ):
                raise ValidationError("This competitor relationship requires a lost outcome.")
        now = timezone.now()
        outcome = None
        if locked_target.stage_kind in {"won", "lost"}:
            recorded_by = user if getattr(user, "is_authenticated", False) else None
            outcome = OpportunityOutcome(
                tenant_id=tenant_id,
                opportunity=locked_opportunity,
                result=locked_target.stage_kind,
                reason=locked_reason,
                competitor_link=locked_competitor,
                notes=notes,
                closed_at=now,
                recorded_by=recorded_by,
            )
            outcome.full_clean()
            outcome.save()
        locked_placement.current_stage = locked_target
        locked_placement.probability_override = None
        locked_placement.stage_entered_at = now
        locked_placement.full_clean()
        locked_placement.save()
        locked_opportunity.stage = locked_target.crm_stage_key
        locked_opportunity.probability = locked_target.probability
        locked_opportunity.forecast_category = locked_target.forecast_category
        locked_opportunity.save()
        write_audit_log(
            user,
            locked_placement,
            "update",
            {
                "operation": "transition",
                "opportunity_id": locked_opportunity.pk,
                "from_stage_id": locked_current.pk,
                "to_stage_id": locked_target.pk,
                "result": locked_target.stage_kind if locked_target.stage_kind in {"won", "lost"} else None,
                "reason_id": locked_reason.pk if locked_reason is not None else None,
                "competitor_link_id": locked_competitor.pk if locked_competitor is not None else None,
                "outcome_id": outcome.pk if outcome is not None else None,
            },
            tenant=tenant,
        )
    return locked_placement
