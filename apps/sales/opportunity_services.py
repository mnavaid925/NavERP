from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.models.OpportunityPipeline.Pipelines import (
    PIPELINE_CRITERION_CHOICES,
    OpportunityPipelinePlacement,
    Pipeline,
    PipelineStage,
)


def _opportunity_pipeline_tenant_id(tenant):
    return getattr(tenant, "pk", tenant)


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


def _opportunity_pipeline_validate_active_shape(pipeline):
    active_stages = PipelineStage.objects.filter(
        tenant=pipeline.tenant,
        pipeline=pipeline,
        is_active=True,
    )
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


def sales_validate_stage_criteria(stage, opportunity, active_team_member=False):
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
    missing = []
    for item in stage.entry_criteria or []:
        if isinstance(item, dict) and item.get("key") in checks and not checks[item["key"]]:
            missing.append(item.get("label") or item["key"])
    if missing:
        raise ValidationError("Stage entry criteria are not met: " + ", ".join(missing))
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
