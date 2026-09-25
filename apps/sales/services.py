from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.crm.models import CrmTask, Lead, Opportunity
from apps.sales.models import (
    LeadNurtureEnrollment,
    LeadQualification,
    LeadRoutingRule,
    LeadScoreEvent,
)


EVENT_DELTAS = {
    "form_submitted": 5,
    "email_open": 2,
    "email_click": 8,
    "web_visit": 1,
    "content_download": 6,
    "event_attendance": 4,
    "meeting_booked": 10,
    "demo_request": 15,
    "call_connected": 8,
    "reply_received": 12,
    "fit_match": 20,
    "fit_mismatch": -15,
    "unsubscribe": -25,
    "decay": -5,
}
OPEN_LEAD_STATUSES = ("new", "contacted", "qualified", "recycled")
QUALIFICATION_EVENT_TYPES = {
    "qualified": "fit_match",
    "disqualified": "fit_mismatch",
}
NURTURE_EXIT_REASONS = {
    "completed": {"completed"},
    "cancelled": {"cancelled", "qualified", "disqualified", "unsubscribed", "bounced", "manual"},
    "replied": {"replied"},
    "converted": {"converted"},
}


def _tenant_id(tenant):
    return getattr(tenant, "pk", tenant)


def _same_tenant(record, tenant):
    return record is not None and record.tenant_id == _tenant_id(tenant)


def _is_admin(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def _active_tenant_user(user, tenant):
    return (
        user is not None
        and user.tenant_id == _tenant_id(tenant)
        and getattr(user, "is_active", False)
    )


def score_rating(score):
    score = max(0, min(100, int(score or 0)))
    return "hot" if score >= 70 else "warm" if score >= 40 else "cold"


def project_lead_score(lead, tenant, at=None):
    at = at or timezone.now()
    total = LeadScoreEvent.objects.filter(
        lead=lead,
        tenant=tenant,
        occurred_at__lte=at,
    ).filter(Q(effective_until__isnull=True) | Q(effective_until__gt=at)).aggregate(total=Sum("score_delta"))["total"] or 0
    return max(0, min(100, int(total)))


def _default_event_category(event_type):
    if event_type in {"fit_match", "fit_mismatch"}:
        return "qualification"
    if event_type in {"manual_adjustment", "correction"}:
        return "manual" if event_type == "manual_adjustment" else "correction"
    if event_type == "decay":
        return "decay"
    return "behavioral"


def _same_score_event_payload(existing, *, lead, event_type, score_delta, signal_category, source_kind, source_ref, reason, effective_until, corrects_event, recorded_by):
    return (
        existing.lead_id == lead.pk
        and existing.event_type == event_type
        and existing.score_delta == score_delta
        and existing.signal_category == signal_category
        and existing.source_kind == source_kind
        and existing.source_ref == source_ref
        and existing.reason == reason
        and existing.effective_until == effective_until
        and existing.corrects_event_id == (corrects_event.pk if corrects_event is not None else None)
        and existing.recorded_by_id == (recorded_by.pk if recorded_by is not None else None)
    )


def record_score_event(lead, tenant, *, event_type, score_delta=None, signal_category=None, source_kind="manual", source_ref="", reason="", effective_until=None, idempotency_key=None, recorded_by=None, corrects_event=None):
    if not _same_tenant(lead, tenant):
        raise ValidationError("The lead must belong to this workspace.")
    if event_type not in dict(LeadScoreEvent.EVENT_TYPE_CHOICES):
        raise ValidationError("Unsupported score event type.")
    reason = reason or ""
    source_ref = source_ref or ""
    if score_delta is None:
        if event_type not in EVENT_DELTAS:
            raise ValidationError("Manual and correction events require a score delta.")
        score_delta = EVENT_DELTAS[event_type]
    if isinstance(score_delta, bool) or not isinstance(score_delta, int):
        raise ValidationError("Score deltas must be integers.")
    if event_type in {"manual_adjustment", "correction"} and not reason.strip():
        raise ValidationError("A reason is required for manual and correction events.")
    if score_delta < -100 or score_delta > 100:
        raise ValidationError("Score deltas must be between -100 and 100.")
    if event_type == "correction" and corrects_event is None:
        raise ValidationError("A correction must identify the event it corrects.")
    if event_type != "correction" and corrects_event is not None:
        raise ValidationError("Only correction events may correct another event.")
    key = idempotency_key.strip() if idempotency_key else None
    signal_category = signal_category or _default_event_category(event_type)
    with transaction.atomic():
        locked_lead = Lead.objects.select_for_update().get(pk=lead.pk, tenant=tenant)
        if key:
            existing = LeadScoreEvent.objects.select_for_update().filter(tenant=tenant, idempotency_key=key).first()
            if existing is not None:
                if not _same_score_event_payload(
                    existing,
                    lead=locked_lead,
                    event_type=event_type,
                    score_delta=score_delta,
                    signal_category=signal_category,
                    source_kind=source_kind,
                    source_ref=source_ref[:255],
                    reason=reason,
                    effective_until=effective_until,
                    corrects_event=corrects_event,
                    recorded_by=recorded_by,
                ):
                    raise ValidationError("That idempotency key was already used for a different score event.")
                return existing
        original = None
        if corrects_event is not None:
            try:
                original = LeadScoreEvent.objects.select_for_update().get(pk=corrects_event.pk, tenant=tenant)
            except ObjectDoesNotExist as exc:
                raise ValidationError("The corrected event does not belong to this workspace.") from exc
            if original.lead_id != locked_lead.pk:
                raise ValidationError("The corrected event must belong to the selected lead.")
            if score_delta != -original.score_delta:
                raise ValidationError("A correction must use the inverse score delta.")
            if LeadScoreEvent.objects.filter(tenant=tenant, corrects_event=original).exists():
                raise ValidationError("That score event has already been corrected.")
        event = LeadScoreEvent(
            tenant=tenant,
            lead=locked_lead,
            signal_category=signal_category,
            event_type=event_type,
            score_delta=score_delta,
            source_kind=source_kind,
            source_ref=source_ref[:255],
            reason=reason,
            effective_until=effective_until,
            idempotency_key=key,
            corrects_event=original,
            recorded_by=recorded_by,
        )
        event.full_clean()
        event.save()
        score = project_lead_score(locked_lead, tenant)
        locked_lead.score = score
        locked_lead.rating = score_rating(score)
        locked_lead.save(update_fields=["score", "rating", "updated_at"])
        write_audit_log(recorded_by, event, "create", {"action": "score_event", "delta": score_delta}, tenant=tenant)
    return event


def recompute_lead_score(lead, tenant, user):
    if not _same_tenant(lead, tenant):
        raise ValidationError("The lead must belong to this workspace.")
    with transaction.atomic():
        locked_lead = Lead.objects.select_for_update().get(pk=lead.pk, tenant=tenant)
        score = project_lead_score(locked_lead, tenant)
        locked_lead.score = score
        locked_lead.rating = score_rating(score)
        locked_lead.save(update_fields=["score", "rating", "updated_at"])
        write_audit_log(user, locked_lead, "update", {"action": "recompute_score", "score": score}, tenant=tenant)
    return score


def _active_qualification_event(lead, tenant, event_type):
    candidates = LeadScoreEvent.objects.filter(
        tenant=tenant,
        lead=lead,
        event_type=event_type,
        source_kind="qualification",
        corrects_event__isnull=True,
    ).order_by("-occurred_at", "-id")
    for event in candidates:
        if not LeadScoreEvent.objects.filter(
            tenant=tenant,
            source_ref__endswith=f":compensate:{event.pk}",
        ).exists():
            return event
    return None


def _last_qualification_event(lead, tenant, event_type):
    return (
        LeadScoreEvent.objects.filter(
            tenant=tenant,
            lead=lead,
            event_type=event_type,
            source_kind="qualification",
        )
        .order_by("-occurred_at", "-id")
        .first()
    )


def _compensate_qualification_event(lead, tenant, user, qualification, event):
    if event is None:
        return
    if LeadScoreEvent.objects.filter(tenant=tenant, corrects_event=event).exists():
        return
    event_type = "fit_mismatch" if event.event_type == "fit_match" else "fit_match"
    record_score_event(
        lead,
        tenant,
        event_type=event_type,
        signal_category="qualification",
        score_delta=-event.score_delta,
        source_kind="qualification",
        source_ref=f"qualification:{qualification.pk}:compensate:{event.pk}",
        reason=f"Compensating qualification transition from {event.get_event_type_display()}",
        recorded_by=user,
        idempotency_key=f"qualification:{qualification.pk}:compensate:{event.pk}",
    )


def apply_qualification_decision(qualification, tenant, user, *, status, disqualification_reason="", notes=""):
    if not _same_tenant(qualification, tenant):
        raise ValidationError("The assessment must belong to this workspace.")
    if status not in dict(LeadQualification.STATUS_CHOICES):
        raise ValidationError("Unsupported qualification status.")
    if status == "archived" and not _is_admin(user):
        raise ValidationError("Tenant administrator access is required to archive an assessment.")
    with transaction.atomic():
        lead = Lead.objects.select_for_update().get(pk=qualification.lead_id, tenant=tenant)
        locked = LeadQualification.objects.select_for_update().get(pk=qualification.pk, tenant=tenant)
        if lead.status == "converted":
            raise ValidationError("A converted lead cannot be re-qualified.")
        if locked.status == "archived":
            raise ValidationError("Archived assessments cannot be reopened.")
        previous_status = locked.status
        if status == previous_status:
            return locked
        previous_event = None
        if previous_status in QUALIFICATION_EVENT_TYPES:
            previous_event = _active_qualification_event(lead, tenant, QUALIFICATION_EVENT_TYPES[previous_status])
            _compensate_qualification_event(lead, tenant, user, locked, previous_event)
        locked.status = status
        locked.disqualification_reason = disqualification_reason if status == "disqualified" else ""
        if notes:
            locked.notes = notes
        locked.assessed_by = user
        locked.assessed_at = timezone.now()
        locked.full_clean()
        locked.save()
        if status in {"qualified", "disqualified"}:
            event_type = QUALIFICATION_EVENT_TYPES[status]
            target_event = _last_qualification_event(lead, tenant, event_type)
            token = target_event.pk if target_event is not None else "initial"
            record_score_event(
                lead,
                tenant,
                event_type=event_type,
                source_kind="qualification",
                reason=f"Qualification marked {status.replace('_', ' ')}",
                recorded_by=user,
                idempotency_key=f"qualification:{locked.pk}:{status}:{token}",
            )
            lead.status = "qualified" if status == "qualified" else "unqualified"
            lead.save(update_fields=["status", "updated_at"])
            exit_nurture_for_lead(lead, tenant, user, status)
        if status == "qualified":
            route_lead(lead, tenant, user)
        write_audit_log(user, locked, "update", {"action": "qualification_decision", "status": status}, tenant=tenant)
    return locked


def _routing_values(lead, qualification):
    return {
        "source": lead.source,
        "status": lead.status,
        "rating": lead.rating,
        "score": lead.score,
        "est_value": lead.est_value,
        "owner_id": lead.owner_id,
        "company": lead.company,
        "title": lead.title,
        "email_present": bool(lead.email),
        "phone_present": bool(lead.phone),
        "qualification_status": qualification.status if qualification else None,
        "framework": qualification.framework if qualification else None,
        "country_code": qualification.country_code if qualification else None,
        "region": qualification.region if qualification else None,
        "city": qualification.city if qualification else None,
        "industry": qualification.industry if qualification else None,
        "employee_count": qualification.employee_count if qualification else None,
        "seniority": qualification.seniority if qualification else None,
        "budget_status": qualification.budget_status if qualification else None,
        "authority_level": qualification.authority_level if qualification else None,
        "expected_purchase_on": qualification.expected_purchase_on if qualification else None,
    }


def _condition_matches(actual, operator, expected):
    if operator == "is_set":
        return (actual not in (None, "")) if expected is not False else (actual in (None, ""))
    if operator == "is_empty":
        return (actual in (None, "")) if expected is not False else (actual not in (None, ""))
    if operator in {"in", "not_in"}:
        if not isinstance(expected, list):
            return False
        try:
            return (actual in expected) if operator == "in" else (actual not in expected)
        except TypeError:
            return False
    if operator == "contains":
        return str(expected) in str(actual or "")
    if operator == "icontains":
        return str(expected).casefold() in str(actual or "").casefold()
    try:
        if isinstance(actual, Decimal) or isinstance(expected, (int, float, Decimal)):
            left = Decimal(str(actual))
            right = Decimal(str(expected))
            if operator == "gt":
                return left > right
            if operator == "gte":
                return left >= right
            if operator == "lt":
                return left < right
            if operator == "lte":
                return left <= right
            if operator == "eq":
                return left == right
            if operator == "ne":
                return left != right
    except (InvalidOperation, TypeError, ValueError):
        pass
    if operator == "eq":
        return str(actual or "") == str(expected or "")
    if operator == "ne":
        return str(actual or "") != str(expected or "")
    return False


def _rule_matches(rule, lead, qualification):
    if not rule.conditions:
        return True
    values = _routing_values(lead, qualification)
    results = []
    for condition in rule.conditions:
        if not isinstance(condition, dict) or not {"field", "operator", "value"}.issubset(condition):
            return False
        results.append(_condition_matches(values.get(condition["field"]), condition["operator"], condition["value"]))
    return all(results) if rule.match_mode == "all" else any(results)


def _candidate_owner(rule, lead, lock=False):
    if rule.assignment_mode == "fixed_owner":
        return rule.default_owner if _active_tenant_user(rule.default_owner, lead.tenant) else None
    if rule.assignment_mode == "territory_manager":
        manager = rule.territory.manager if rule.territory_id else None
        return manager if _active_tenant_user(manager, lead.tenant) else None
    owner_queryset = rule.eligible_owners.filter(tenant=lead.tenant, is_active=True)
    if lock:
        owner_queryset = owner_queryset.select_for_update()
    owners = list(owner_queryset.order_by("pk"))
    if not owners:
        return None
    if rule.max_open_leads is not None:
        owner_ids = [owner.pk for owner in owners]
        counts = {
            row["owner_id"]: row["count"]
            for row in Lead.objects.filter(
                tenant=lead.tenant,
                owner_id__in=owner_ids,
                status__in=OPEN_LEAD_STATUSES,
            )
            .exclude(pk=lead.pk)
            .values("owner_id")
            .annotate(count=Count("id"))
        }
        owners = [owner for owner in owners if counts.get(owner.pk, 0) < rule.max_open_leads]
    if not owners:
        return rule.fallback_owner if _active_tenant_user(rule.fallback_owner, lead.tenant) else None
    index = rule.cursor % len(owners)
    return owners[index]


def _routing_ineligible_reason(lead, qualification):
    if lead.status == "converted":
        return "Converted leads cannot be routed."
    if qualification is not None and qualification.status == "archived":
        return "Archived assessments cannot be routed."
    return None


def preview_routing(lead, tenant, rule=None):
    if not _same_tenant(lead, tenant):
        raise ValidationError("The lead must belong to this workspace.")
    qualification = LeadQualification.objects.filter(tenant=tenant, lead=lead).first()
    ineligible = _routing_ineligible_reason(lead, qualification)
    if ineligible:
        return {"rule": None, "matched": False, "owner": None, "reason": ineligible}
    if rule is not None:
        rules = [rule] if rule.tenant_id == _tenant_id(tenant) and rule.is_active else []
    else:
        rules = list(LeadRoutingRule.objects.filter(tenant=tenant, is_active=True).prefetch_related("eligible_owners").order_by("priority", "id"))
    for candidate_rule in rules:
        if _rule_matches(candidate_rule, lead, qualification):
            owner = _candidate_owner(candidate_rule, lead)
            return {"rule": candidate_rule, "matched": True, "owner": owner, "reason": "Rule matched this lead."}
    return {"rule": None, "matched": False, "owner": None, "reason": "No active routing rule matched this lead."}


def _routing_task(lead, tenant, owner, rule):
    subject = f"Follow up {lead.number}"
    task = CrmTask.objects.filter(tenant=tenant, subject=subject, owner=owner, status__in=["open", "in_progress"]).order_by("pk").first()
    if task is None:
        task = CrmTask.objects.create(
            tenant=tenant,
            subject=subject,
            type="follow_up",
            priority="medium",
            status="open",
            owner=owner,
            description=f"Sales routing rule {rule.name} assigned this lead.",
            due_date=timezone.localdate() + timedelta(days=1),
        )
    return task


def _update_routing_metadata(rule, owner, changed):
    if rule.assignment_mode == "round_robin" and changed:
        owners = list(rule.eligible_owners.filter(tenant=rule.tenant, is_active=True).order_by("pk"))
        if owners:
            index = owners.index(owner) if owner in owners else rule.cursor
            rule.cursor = (index + 1) % len(owners)
    rule.last_assigned_owner = owner
    rule.last_assigned_at = timezone.now()
    rule.save(update_fields=["cursor", "last_assigned_owner", "last_assigned_at", "updated_at"])


def route_lead(lead, tenant, user, rule=None):
    if not _same_tenant(lead, tenant):
        raise ValidationError("The lead must belong to this workspace.")
    with transaction.atomic():
        locked_lead = Lead.objects.select_for_update().get(pk=lead.pk, tenant=tenant)
        qualification = LeadQualification.objects.select_for_update().filter(tenant=tenant, lead=locked_lead).first()
        ineligible = _routing_ineligible_reason(locked_lead, qualification)
        if ineligible:
            return {"matched": False, "owner": None, "rule": None, "changed": False, "reason": ineligible}
        if rule is None:
            rules = list(LeadRoutingRule.objects.select_for_update().filter(tenant=tenant, is_active=True).prefetch_related("eligible_owners").order_by("priority", "id"))
        else:
            locked_rule = LeadRoutingRule.objects.select_for_update().get(pk=rule.pk, tenant=tenant)
            rules = [locked_rule]
        for candidate_rule in rules:
            if not candidate_rule.is_active or not _rule_matches(candidate_rule, locked_lead, qualification):
                continue
            owner = _candidate_owner(candidate_rule, locked_lead, lock=True)
            if owner is None or not _active_tenant_user(owner, tenant):
                return {"matched": True, "owner": None, "rule": candidate_rule, "changed": False, "reason": "No eligible owner was available."}
            changed = locked_lead.owner_id != owner.pk
            if changed:
                locked_lead.owner = owner
                locked_lead.save(update_fields=["owner", "updated_at"])
            _update_routing_metadata(candidate_rule, owner, changed)
            if changed:
                _routing_task(locked_lead, tenant, owner, candidate_rule)
                write_audit_log(user, locked_lead, "update", {"action": "route", "rule": candidate_rule.name, "owner": owner.pk}, tenant=tenant)
                reason = "Owner assigned."
            else:
                reason = "The lead already has this owner."
            return {"matched": True, "owner": owner, "rule": candidate_rule, "changed": changed, "reason": reason}
    return {"matched": False, "owner": None, "rule": None, "changed": False, "reason": "No active routing rule matched this lead."}


def activate_nurture(enrollment, tenant, user, next_touch_at=None):
    if not _same_tenant(enrollment, tenant):
        raise ValidationError("The enrollment must belong to this workspace.")
    if not _is_admin(user):
        raise ValidationError("Tenant administrator access is required to activate nurture.")
    with transaction.atomic():
        locked_lead = Lead.objects.select_for_update().get(pk=enrollment.lead_id, tenant=tenant)
        locked = LeadNurtureEnrollment.objects.select_for_update().get(pk=enrollment.pk, tenant=tenant)
        if locked_lead.status == "converted":
            raise ValidationError("A converted lead cannot enter nurture.")
        if locked.email_campaign.tenant_id != _tenant_id(tenant) or locked.email_campaign.send_type != "drip":
            raise ValidationError("Nurture enrollment requires a CRM drip campaign from this workspace.")
        if not locked.consent_purpose_id or locked.consent_purpose.tenant_id != _tenant_id(tenant) or not locked.consent_purpose.is_active:
            raise ValidationError("Choose an active consent purpose before activation.")
        if locked.consent_purpose.is_optional and not locked.consent_evidence.strip():
            raise ValidationError("Consent evidence is required for an optional purpose.")
        if locked.status not in {"pending", "paused"}:
            raise ValidationError("Only pending or paused enrollments can be activated.")
        previous_status = locked.status
        locked.status = "active"
        locked.started_at = locked.started_at or timezone.now()
        locked.score_at_enrollment = locked_lead.score
        if next_touch_at is not None or previous_status == "pending":
            locked.next_touch_at = next_touch_at
        locked.exit_reason = ""
        locked.full_clean()
        locked.save(update_fields=["status", "started_at", "score_at_enrollment", "next_touch_at", "exit_reason", "updated_at"])
        write_audit_log(user, locked, "update", {"action": "activate_nurture"}, tenant=tenant)
    return locked


def _valid_nurture_reason(target_status, reason):
    return reason in NURTURE_EXIT_REASONS.get(target_status, set())


def transition_nurture(enrollment, tenant, user, target_status, exit_reason="", notes=""):
    if not _same_tenant(enrollment, tenant):
        raise ValidationError("The enrollment must belong to this workspace.")
    with transaction.atomic():
        locked_lead = Lead.objects.select_for_update().get(pk=enrollment.lead_id, tenant=tenant)
        locked = LeadNurtureEnrollment.objects.select_for_update().get(pk=enrollment.pk, tenant=tenant)
        allowed = {
            "active": {"pending", "paused"},
            "paused": {"active"},
            "completed": {"active", "paused"},
            "cancelled": {"pending", "active", "paused"},
            "replied": {"active", "paused"},
            "converted": {"active", "paused"},
        }
        if target_status not in allowed or locked.status not in allowed[target_status]:
            raise ValidationError("That nurture transition is not available.")
        if target_status == "active":
            if locked.status != "paused":
                raise ValidationError("Only a paused enrollment can be resumed.")
            if not _is_admin(user):
                raise ValidationError("Tenant administrator access is required to resume nurture.")
            return activate_nurture(locked, tenant, user, next_touch_at=locked.next_touch_at)
        if target_status == "converted":
            if locked_lead.status != "converted" or not Opportunity.objects.filter(tenant=tenant, source_lead=locked_lead).exists():
                raise ValidationError("A nurture conversion exit requires a verified CRM conversion.")
        if target_status in {"completed", "cancelled", "replied", "converted"}:
            if not _valid_nurture_reason(target_status, exit_reason):
                raise ValidationError("That exit reason is not valid for this transition.")
        locked.status = target_status
        locked.exit_reason = exit_reason
        if notes:
            locked.notes = notes
        if target_status in {"completed", "cancelled", "replied", "converted"}:
            locked.completed_at = timezone.now()
        locked.full_clean()
        locked.save(update_fields=["status", "exit_reason", "notes", "completed_at", "updated_at"])
        write_audit_log(user, locked, "update", {"action": "nurture_transition", "status": target_status}, tenant=tenant)
    return locked


def exit_nurture_for_lead(lead, tenant, user, reason):
    if not _same_tenant(lead, tenant):
        raise ValidationError("The lead must belong to this workspace.")
    if reason not in {"qualified", "disqualified", "replied", "converted", "unsubscribed", "bounced", "cancelled", "completed", "manual"}:
        raise ValidationError("Unsupported nurture exit reason.")
    target_status = "converted" if reason == "converted" else "replied" if reason == "replied" else "cancelled"
    Lead.objects.select_for_update().get(pk=lead.pk, tenant=tenant)
    for enrollment in LeadNurtureEnrollment.objects.filter(tenant=tenant, lead=lead, status__in=["active", "paused"]).select_for_update():
        transition_nurture(enrollment, tenant, user, target_status, exit_reason=reason)


def _ensure_handoff_task(lead, tenant, owner, opportunity):
    subject = f"Follow up {lead.number}"
    task = CrmTask.objects.select_for_update().filter(tenant=tenant, subject=subject, owner=owner, status__in=["open", "in_progress"]).order_by("pk").first()
    if task is not None:
        updates = []
        if task.related_opportunity_id != opportunity.pk:
            task.related_opportunity = opportunity
            updates.append("related_opportunity")
        if task.priority != "high":
            task.priority = "high"
            updates.append("priority")
        if updates:
            task.save(update_fields=[*updates, "updated_at"])
        return task
    return CrmTask.objects.create(
        tenant=tenant,
        subject=subject,
        type="follow_up",
        priority="high",
        status="open",
        owner=owner,
        related_opportunity=opportunity,
        description=f"Sales handoff created from qualified lead {lead.number}.",
        due_date=timezone.localdate() + timedelta(days=1),
    )


def handoff_lead(lead, tenant, user):
    if not _same_tenant(lead, tenant):
        raise ValidationError("The lead must belong to this workspace.")
    with transaction.atomic():
        locked_lead = Lead.objects.select_for_update().get(pk=lead.pk, tenant=tenant)
        qualification = LeadQualification.objects.select_for_update().filter(tenant=tenant, lead=locked_lead).first()
        if qualification is None or qualification.status != "qualified":
            raise ValidationError("A qualified assessment is required before handoff.")
        already_converted = locked_lead.status == "converted"
        from apps.crm.services import convert_lead
        opportunity = convert_lead(locked_lead, tenant)
        locked_lead.refresh_from_db()
        if locked_lead.status != "converted" or not Opportunity.objects.filter(pk=opportunity.pk, tenant=tenant, source_lead=locked_lead).exists():
            raise ValidationError("CRM conversion could not be verified.")
        exit_nurture_for_lead(locked_lead, tenant, user, "converted")
        _ensure_handoff_task(locked_lead, tenant, locked_lead.owner, opportunity)
        if not already_converted:
            write_audit_log(user, locked_lead, "update", {"action": "sales_handoff", "opportunity": opportunity.number}, tenant=tenant)
    return opportunity


def _enrichment_event_payload(event):
    from apps.sales.models.ContactAccountManagement.PartyEnrichment import (
        sanitize_enrichment_text,
        validate_enrichment_changes,
    )

    confidence = event.match_confidence
    try:
        normalized_confidence = Decimal(str(confidence)) if confidence is not None else None
    except (InvalidOperation, TypeError, ValueError):
        normalized_confidence = None
    return {
        "party_id": event.party_id,
        "kind": event.kind,
        "source_kind": event.source_kind,
        "source_name": sanitize_enrichment_text(event.source_name, field_name="source_name", max_length=120, allow_url=False),
        "source_reference": sanitize_enrichment_text(event.source_reference, field_name="source_reference", max_length=255, allow_url=False),
        "changes": validate_enrichment_changes(event.changes or {}),
        "legal_basis_purpose_id": event.legal_basis_purpose_id,
        "requested_by_id": event.requested_by_id,
        "match_confidence": normalized_confidence,
        "error_code": event.error_code,
        "error_summary": sanitize_enrichment_text(event.error_summary, field_name="error_summary", max_length=255),
    }


def _enrichment_request_matches(existing, request_payload):
    existing_payload = _enrichment_event_payload(existing)
    comparable_request = dict(request_payload)
    if existing.status != "proposed":
        existing_payload.pop("error_summary", None)
        comparable_request.pop("error_summary", None)
    return existing_payload == comparable_request


def _enrichment_request_payload(party, kind, source_kind, source_name, source_reference, changes, legal_basis_purpose, user, match_confidence, error_code, error_summary):
    from apps.sales.models.ContactAccountManagement.PartyEnrichment import sanitize_enrichment_text

    confidence = None
    if match_confidence is not None:
        try:
            confidence = Decimal(str(match_confidence))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError("Match confidence must be a finite value between 0 and 1.") from exc
        if not confidence.is_finite() or not 0 <= confidence <= 1:
            raise ValidationError("Match confidence must be a finite value between 0 and 1.")
    return {
        "party_id": party.pk,
        "kind": kind,
        "source_kind": source_kind,
        "source_name": sanitize_enrichment_text(source_name, field_name="source_name", max_length=120, allow_url=False),
        "source_reference": sanitize_enrichment_text(source_reference, field_name="source_reference", max_length=255, allow_url=False),
        "changes": changes,
        "legal_basis_purpose_id": getattr(legal_basis_purpose, "pk", None),
        "requested_by_id": getattr(user, "pk", None),
        "match_confidence": confidence,
        "error_code": (error_code or "").strip(),
        "error_summary": sanitize_enrichment_text(error_summary, field_name="error_summary", max_length=255),
    }


def create_enrichment_event(tenant, user, *, party, kind, source_kind, source_name="", source_reference="", changes=None, legal_basis_purpose=None, status="proposed", match_confidence=None, idempotency_key=None, error_code="", error_summary=""):
    from apps.core.models import Party
    from apps.sales.models.ContactAccountManagement.PartyEnrichment import (
        EXTERNAL_SOURCE_KINDS,
        PartyEnrichmentEvent,
        validate_enrichment_changes,
        validate_enrichment_fields_for_party,
    )

    if status != "proposed":
        raise ValidationError("Enrichment requests must start as proposed.")
    if not _active_tenant_user(user, tenant):
        raise ValidationError("An active workspace user is required.")
    if not _same_tenant(party, tenant):
        raise ValidationError("The enrichment Party must belong to this workspace.")
    if legal_basis_purpose is not None and not _same_tenant(legal_basis_purpose, tenant):
        raise ValidationError("The lawful basis purpose must belong to this workspace.")
    if kind not in dict(PartyEnrichmentEvent.KIND_CHOICES):
        raise ValidationError("Unsupported enrichment kind.")
    if source_kind not in dict(PartyEnrichmentEvent.SOURCE_KIND_CHOICES):
        raise ValidationError("Unsupported enrichment source.")
    normalized_changes = validate_enrichment_changes(changes or {})
    if idempotency_key is not None and not isinstance(idempotency_key, str):
        raise ValidationError("The enrichment idempotency key must be text.")
    key = (idempotency_key or "").strip() or None
    if key and len(key) > 120:
        raise ValidationError("The enrichment idempotency key cannot exceed 120 characters.")
    with transaction.atomic():
        from apps.accounts.models import User

        try:
            locked_user = User.objects.select_for_update().get(
                pk=user.pk,
                tenant=tenant,
                is_active=True,
            )
        except ObjectDoesNotExist as exc:
            raise ValidationError("An active workspace user is required.") from exc
        try:
            locked_party = Party.objects.select_for_update().get(pk=party.pk, tenant=tenant)
        except ObjectDoesNotExist as exc:
            raise ValidationError("The enrichment Party must belong to this workspace.") from exc
        validate_enrichment_fields_for_party(locked_party, normalized_changes)
        locked_purpose = None
        purpose_id = getattr(legal_basis_purpose, "pk", None)
        if purpose_id:
            from apps.core.models import ConsentPurpose
            try:
                locked_purpose = ConsentPurpose.objects.select_for_update().get(
                    pk=purpose_id,
                    tenant=tenant,
                    is_active=True,
                )
            except ObjectDoesNotExist as exc:
                raise ValidationError("Choose an active purpose from this workspace.") from exc

        if source_kind in EXTERNAL_SOURCE_KINDS and locked_purpose is None:
            raise ValidationError("External enrichment requires an active lawful basis purpose.")
        request_payload = _enrichment_request_payload(
            locked_party,
            kind,
            source_kind,
            source_name,
            source_reference,
            normalized_changes,
            locked_purpose,
            locked_user,
            match_confidence,
            error_code,
            error_summary,
        )
        if key:
            existing = PartyEnrichmentEvent.objects.select_for_update().filter(
                tenant=tenant,
                idempotency_key=key,
            ).first()
            if existing is not None:
                if not _enrichment_request_matches(existing, request_payload):
                    raise ValidationError("That idempotency key was already used for different enrichment evidence.")
                return existing
        event = PartyEnrichmentEvent(
            tenant=tenant,
            party=locked_party,
            kind=kind,
            source_kind=source_kind,
            source_name=request_payload["source_name"],
            source_reference=request_payload["source_reference"],
            status="proposed",
            match_confidence=request_payload["match_confidence"],
            changes=normalized_changes,
            legal_basis_purpose=locked_purpose,
            requested_by=locked_user,
            idempotency_key=key,
            error_code=request_payload["error_code"],
            error_summary=request_payload["error_summary"],
        )
        try:
            with transaction.atomic():
                event.full_clean(validate_unique=False)
                event.save(force_insert=True)
        except IntegrityError:
            if not key:
                raise
            existing = PartyEnrichmentEvent.objects.select_for_update().get(
                tenant=tenant,
                idempotency_key=key,
            )
            if _enrichment_event_payload(existing) != request_payload:
                raise ValidationError("That idempotency key was already used for different enrichment evidence.")
            return existing
        write_audit_log(
            locked_user,
            event,
            "create",
            {
                "action": "enrichment_proposal",
                "kind": kind,
                "source_kind": source_kind,
                "status": "proposed",
                "fields": sorted(normalized_changes),
            },
            tenant=tenant,
        )
    return event


def _enrichment_canonical_values(party, *, lock=False):
    from apps.core.models import ContactMethod
    from apps.crm.models import AccountProfile, ContactProfile

    values = {}
    contact_queryset = ContactProfile.objects.filter(tenant=party.tenant, party=party)
    account_queryset = AccountProfile.objects.filter(tenant=party.tenant, party=party)
    method_queryset = ContactMethod.objects.filter(tenant=party.tenant, party=party)
    if lock:
        contact_queryset = contact_queryset.select_for_update()
        account_queryset = account_queryset.select_for_update()
        method_queryset = method_queryset.select_for_update()
    contact_profile = contact_queryset.order_by("pk").first()
    account_profile = account_queryset.order_by("pk").first()
    if contact_profile:
        values.update(
            job_title=contact_profile.job_title,
            department=contact_profile.department,
            linkedin=contact_profile.linkedin,
            work_email=contact_profile.email,
            phone=contact_profile.phone,
            mobile=contact_profile.mobile,
        )
    if account_profile:
        values.update(
            website=account_profile.website,
            industry=account_profile.industry,
            employee_count=account_profile.employee_count,
            annual_revenue=account_profile.annual_revenue,
        )
    for method in method_queryset.order_by("pk"):
        field_name = {"email": "work_email", "phone": "phone", "mobile": "mobile"}.get(method.kind)
        if field_name:
            values[field_name] = method.value
    return values


def _apply_enrichment_value(party, field_name, value):
    from apps.core.models import ContactMethod
    from apps.crm.models import AccountProfile, ContactProfile
    from apps.sales.models.ContactAccountManagement.PartyEnrichment import validate_enrichment_changes

    value = validate_enrichment_changes({field_name: {"value": value}})[field_name]["value"]
    if field_name in {"work_email", "phone", "mobile"}:
        if party.kind != "person":
            raise ValidationError(f"{field_name} can only be applied to a person Party.")
        kind = {"work_email": "email", "phone": "phone", "mobile": "mobile"}[field_name]
        method = ContactMethod.objects.select_for_update().filter(
            tenant=party.tenant,
            party=party,
            kind=kind,
        ).order_by("pk").first()
        if method is None:
            method = ContactMethod(tenant=party.tenant, party=party, kind=kind, value=str(value))
            method.save()
        else:
            method.value = str(value)
            method.save(update_fields=["value"])
        profile = ContactProfile.objects.select_for_update().filter(
            tenant=party.tenant,
            party=party,
        ).order_by("pk").first()
        if profile is None:
            profile = ContactProfile(tenant=party.tenant, party=party)
        setattr(profile, "email" if field_name == "work_email" else field_name, str(value))
        profile.save()
        return
    if field_name in {"job_title", "department", "linkedin"}:
        if party.kind != "person":
            raise ValidationError(f"{field_name} can only be applied to a person Party.")
        profile = ContactProfile.objects.select_for_update().filter(
            tenant=party.tenant,
            party=party,
        ).order_by("pk").first()
        if profile is None:
            profile = ContactProfile(tenant=party.tenant, party=party)
        setattr(profile, field_name, str(value))
        profile.save()
        return
    if field_name in {"website", "industry", "employee_count", "annual_revenue"}:
        if party.kind != "organization":
            raise ValidationError(f"{field_name} can only be applied to an organization Party.")
        profile = AccountProfile.objects.select_for_update().filter(
            tenant=party.tenant,
            party=party,
        ).order_by("pk").first()
        if profile is None:
            profile = AccountProfile(tenant=party.tenant, party=party)
        if field_name == "annual_revenue":
            try:
                value = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValidationError("Annual revenue must be a finite decimal value.") from exc
            if not value.is_finite() or value < 0 or value > Decimal("999999999999.99"):
                raise ValidationError("Annual revenue is outside the supported range.")
        setattr(profile, field_name, value)
        profile.save()
        return
    raise ValidationError(f"Unsupported enrichment field: {field_name}.")


def apply_enrichment_event(event, tenant, user, selected_fields, review_note=""):
    from apps.core.models import ConsentPurpose, Party
    from apps.sales.models.ContactAccountManagement.PartyEnrichment import (
        PartyEnrichmentEvent,
        validate_enrichment_changes,
        validate_enrichment_fields_for_party,
    )

    if not _is_admin(user) or not _active_tenant_user(user, tenant):
        raise ValidationError("Tenant administrator access is required to apply enrichment.")
    if not _same_tenant(event, tenant):
        raise ValidationError("The enrichment event must belong to this workspace.")
    try:
        fields = tuple(dict.fromkeys(selected_fields or ()))
    except TypeError as exc:
        raise ValidationError("Choose at least one valid proposed field.") from exc
    if not fields or any(not isinstance(field, str) for field in fields):
        raise ValidationError("Choose at least one valid proposed field.")
    with transaction.atomic():
        from apps.accounts.models import User

        try:
            locked_user = User.objects.select_for_update().get(
                pk=user.pk,
                tenant=tenant,
                is_active=True,
            )
        except ObjectDoesNotExist as exc:
            raise ValidationError("An active workspace user is required.") from exc
        if not (locked_user.is_superuser or locked_user.is_tenant_admin):
            raise ValidationError("Tenant administrator access is required to apply enrichment.")
        try:
            locked = PartyEnrichmentEvent.objects.select_for_update().get(pk=event.pk, tenant=tenant)
        except ObjectDoesNotExist as exc:
            raise ValidationError("The enrichment event does not exist in this workspace.") from exc
        if locked.status != "proposed":
            raise ValidationError("Only proposed enrichment events can be applied.")
        try:
            locked_party = Party.objects.select_for_update().get(pk=locked.party_id, tenant=tenant)
        except ObjectDoesNotExist as exc:
            raise ValidationError("The enrichment Party no longer exists in this workspace.") from exc
        if locked.legal_basis_purpose_id:
            purpose = ConsentPurpose.objects.select_for_update().filter(
                pk=locked.legal_basis_purpose_id,
                tenant=tenant,
                is_active=True,
            ).first()
            if purpose is None:
                raise ValidationError("The lawful basis purpose is no longer active.")
        changes = validate_enrichment_changes(locked.changes)
        validate_enrichment_fields_for_party(locked_party, changes)
        if any(field not in changes for field in fields):
            raise ValidationError("Choose at least one valid proposed field.")
        canonical = _enrichment_canonical_values(locked_party, lock=True)
        for field_name in fields:
            proposed = changes[field_name]["value"]
            current = canonical.get(field_name)
            if current not in (None, "") and str(current) != str(proposed):
                raise ValidationError(f"{field_name} already has a protected canonical value.")
        for field_name in fields:
            _apply_enrichment_value(locked_party, field_name, changes[field_name]["value"])
        locked.party = locked_party
        locked.status = "applied"
        locked.reviewed_by = locked_user
        locked.applied_at = timezone.now()
        locked._allow_status_transition = True
        try:
            locked.full_clean(validate_unique=False)
            locked.save(update_fields=["status", "reviewed_by", "applied_at"])
        finally:
            locked._allow_status_transition = False
        write_audit_log(
            locked_user,
            locked,
            "update",
            {"action": "enrichment_apply", "fields": sorted(fields), "review_note_present": bool((review_note or "").strip())},
            tenant=tenant,
        )
    return locked


def reject_enrichment_event(event, tenant, user, review_note):
    from apps.core.models import Party
    from apps.sales.models.ContactAccountManagement.PartyEnrichment import (
        PartyEnrichmentEvent,
        sanitize_enrichment_text,
    )

    if not _active_tenant_user(user, tenant):
        raise ValidationError("An active workspace user is required.")
    if not _same_tenant(event, tenant):
        raise ValidationError("The enrichment event must belong to this workspace.")
    if not (review_note or "").strip():
        raise ValidationError("A rejection reason is required.")
    with transaction.atomic():
        from apps.accounts.models import User

        try:
            locked_user = User.objects.select_for_update().get(
                pk=user.pk,
                tenant=tenant,
                is_active=True,
            )
            locked = PartyEnrichmentEvent.objects.select_for_update().get(pk=event.pk, tenant=tenant)
        except ObjectDoesNotExist as exc:
            raise ValidationError("The enrichment event or reviewer is unavailable in this workspace.") from exc
        try:
            Party.objects.select_for_update().get(pk=locked.party_id, tenant=tenant)
        except ObjectDoesNotExist as exc:
            raise ValidationError("The enrichment Party no longer exists in this workspace.") from exc
        if locked.status != "proposed":
            raise ValidationError("Only proposed enrichment events can be rejected.")
        locked.status = "rejected"
        locked.reviewed_by = locked_user
        locked.error_summary = sanitize_enrichment_text(
            review_note,
            field_name="review_note",
            max_length=255,
        )
        locked._allow_status_transition = True
        try:
            locked.full_clean(validate_unique=False)
            locked.save(update_fields=["status", "reviewed_by", "error_summary"])
        finally:
            locked._allow_status_transition = False
        write_audit_log(
            locked_user,
            locked,
            "update",
            {"action": "enrichment_reject", "reason_present": True},
            tenant=tenant,
        )
    return locked


def _currency_bucket(rollup, code):
    return rollup["currencies"].setdefault(
        code or "unspecified",
        {
            "opportunity": Decimal("0"),
            "weighted": Decimal("0"),
            "orders": Decimal("0"),
            "invoices": Decimal("0"),
        },
    )


def account_rollups(tenant, account_ids):
    from apps.accounting.models import Invoice
    from apps.crm.models import Opportunity
    from apps.scm.models import SalesOrder

    ids = list(dict.fromkeys(account_ids))
    result = {pk: {"currencies": {}} for pk in ids}
    if not ids:
        return result
    weighted = ExpressionWrapper(
        F("amount") * F("probability") / Value(Decimal("100")),
        output_field=DecimalField(max_digits=20, decimal_places=4),
    )
    opportunity_rows = (
        Opportunity.objects.filter(tenant=tenant, account_id__in=ids)
        .values("account_id")
        .annotate(
            opportunity=Sum("amount", filter=Q(stage__in=Opportunity.OPEN_STAGES)),
            weighted=Sum(weighted, filter=Q(stage__in=Opportunity.OPEN_STAGES)),
        )
    )
    for row in opportunity_rows:
        bucket = _currency_bucket(result[row["account_id"]], None)
        bucket["opportunity"] += row["opportunity"] or Decimal("0")
        bucket["weighted"] += row["weighted"] or Decimal("0")
    order_rows = (
        SalesOrder.objects.filter(tenant=tenant, customer_id__in=ids)
        .exclude(status="cancelled")
        .values("customer_id", "currency__code")
        .annotate(orders=Sum("total"))
    )
    for row in order_rows:
        _currency_bucket(result[row["customer_id"]], row["currency__code"])["orders"] += row["orders"] or Decimal("0")
    invoice_rows = (
        Invoice.objects.filter(tenant=tenant, party_id__in=ids)
        .exclude(status="void")
        .values("party_id", "currency__code")
        .annotate(invoices=Sum("total"))
    )
    for row in invoice_rows:
        _currency_bucket(result[row["party_id"]], row["currency__code"])["invoices"] += row["invoices"] or Decimal("0")
    return result


MAX_HIERARCHY_ROWS = 500


def account_hierarchy_rows(tenant):
    from apps.crm.models import AccountProfile

    profiles = list(
        AccountProfile.objects.filter(tenant=tenant, party__tenant=tenant, party__kind="organization")
        .select_related("party", "parent_account")
        .order_by("party__name", "pk")[:MAX_HIERARCHY_ROWS]
    )
    by_party = {profile.party_id: profile for profile in profiles}
    children = {pk: [] for pk in by_party}
    for profile in profiles:
        if profile.parent_account_id in by_party:
            children[profile.parent_account_id].append(profile)
    depth_cache = {}
    invalid_ids = set()
    cycle_ids = set()

    def resolve_depth(start_id):
        if start_id in depth_cache:
            return depth_cache[start_id]
        path = []
        positions = {}
        current_id = start_id
        base_depth = None
        while current_id is not None:
            if current_id in depth_cache:
                base_depth = depth_cache[current_id] + len(path)
                break
            if current_id in positions:
                cycle_ids.update(path[positions[current_id]:])
                invalid_ids.update(path)
                return None
            if len(path) >= AccountProfile.MAX_HIERARCHY_DEPTH:
                invalid_ids.update(path)
                return None
            positions[current_id] = len(path)
            path.append(current_id)
            profile = by_party.get(current_id)
            if profile is None:
                invalid_ids.update(path)
                return None
            current_id = profile.parent_account_id
            if current_id is None:
                base_depth = 0
                break
            if current_id not in by_party:
                invalid_ids.update(path)
                return None
        for party_id in reversed(path):
            depth_cache[party_id] = base_depth
            base_depth += 1
        return depth_cache[start_id]

    for party_id in by_party:
        resolve_depth(party_id)
    rows_by_id = {}
    for profile in profiles:
        valid = profile.party_id not in invalid_ids
        rows_by_id[profile.party_id] = {
            "party": profile.party,
            "profile": profile,
            "parent": by_party[profile.parent_account_id].party if profile.parent_account_id in by_party else None,
            "depth": depth_cache.get(profile.party_id) if valid else None,
            "is_root": profile.parent_account_id is None,
            "is_leaf": not children[profile.party_id],
            "child_count": len(children[profile.party_id]),
            "cycle_detected": profile.party_id in cycle_ids,
            "rollup_available": valid,
            "descendant_count": 0,
            "rollup": {},
        }
    valid_rows = [row for row in rows_by_id.values() if row["rollup_available"]]
    for row in sorted(valid_rows, key=lambda value: value["depth"], reverse=True):
        row["descendant_count"] = sum(
            rows_by_id[child.party_id]["descendant_count"] + 1
            for child in children[row["party"].pk]
            if child.party_id in rows_by_id and rows_by_id[child.party_id]["rollup_available"]
        )
    base_rollups = account_rollups(tenant, list(by_party))
    for row in valid_rows:
        own = base_rollups.get(row["party"].pk, {"currencies": {}})
        row["rollup"] = {
            "currencies": {
                code: dict(values)
                for code, values in own.get("currencies", {}).items()
            }
        }
    for row in sorted(valid_rows, key=lambda value: value["depth"], reverse=True):
        parent_id = row["profile"].parent_account_id
        parent = rows_by_id.get(parent_id)
        if parent is None or not parent["rollup_available"]:
            continue
        for code, values in row["rollup"]["currencies"].items():
            target = _currency_bucket(parent["rollup"], code)
            for field_name, amount in values.items():
                target[field_name] += amount
    return list(rows_by_id.values())


def account_coverage_data(tenant, account=None):
    from apps.crm.models import ContactProfile
    from apps.sales.models.ContactAccountManagement.AccountStakeholders import AccountStakeholder

    if account is not None:
        if getattr(account, "tenant_id", None) != _tenant_id(tenant) or getattr(account, "kind", None) != "organization":
            raise ValidationError("Coverage requires a same-tenant organization account.")
    stakeholders = AccountStakeholder.objects.filter(
        tenant=tenant,
        status="active",
        account__tenant=tenant,
        account__kind="organization",
        contact__tenant=tenant,
        contact__kind="person",
    )
    contacts = ContactProfile.objects.filter(
        tenant=tenant,
        party__tenant=tenant,
        party__kind="person",
    ).filter(account__tenant=tenant, account__kind="organization")
    if account is not None:
        stakeholders = stakeholders.filter(account=account)
        contacts = contacts.filter(account=account)
    roles = {}
    for row in stakeholders.values_list("contact_id", "role"):
        roles.setdefault(row[0], set()).add(row[1])
    primary_ids = set(contacts.values_list("party_id", flat=True))
    coverage = {}
    for party_id in set(roles) | primary_ids:
        coverage[party_id] = {
            "party_id": party_id,
            "primary": party_id in primary_ids,
            "roles": sorted(roles.get(party_id, set())),
        }
    return coverage


def can_manage_account_plan(plan, user):
    return bool(
        _same_tenant(plan, getattr(user, "tenant", None))
        and _active_tenant_user(user, plan.tenant_id)
        and (_is_admin(user) or plan.owner_id == getattr(user, "pk", None))
    )


def save_account_plan(form, tenant, user, *, instance=None):
    from apps.accounts.models import User
    from apps.core.models import Party
    from apps.crm.models import Opportunity
    from apps.sales.models.ContactAccountManagement.AccountPlans import (
        AccountPlan,
        validate_account_plan_opportunities,
    )

    if not _active_tenant_user(user, tenant):
        raise ValidationError("An active workspace user is required.")
    with transaction.atomic():
        try:
            locked_user = User.objects.select_for_update().get(
                pk=user.pk,
                tenant=tenant,
                is_active=True,
            )
        except ObjectDoesNotExist as exc:
            raise ValidationError("An active workspace user is required.") from exc
        if instance is None:
            locked = None
        else:
            try:
                locked = AccountPlan.objects.select_for_update().get(pk=instance.pk, tenant=tenant)
            except ObjectDoesNotExist as exc:
                raise ValidationError("The account plan no longer exists in this workspace.") from exc
            if not (
                _same_tenant(locked, getattr(locked_user, "tenant", None))
                and (_is_admin(locked_user) or locked.owner_id == locked_user.pk)
            ):
                raise ValidationError("Only the plan owner or a tenant administrator can edit this plan.")
            if locked.status == "archived":
                raise ValidationError("Archived account plans are read-only.")
            form.instance = locked
            for field_name in form._meta.fields:
                model_field = form.instance._meta.get_field(field_name)
                if model_field.concrete and not model_field.many_to_many and field_name in form.cleaned_data:
                    setattr(form.instance, field_name, form.cleaned_data[field_name])
        obj = form.save(commit=False)
        obj.tenant = tenant
        if locked is None:
            obj.status = "draft"
        if not _is_admin(locked_user):
            obj.owner = locked_user
        try:
            account = Party.objects.select_for_update().get(
                pk=obj.account_id,
                tenant=tenant,
                kind="organization",
            )
        except ObjectDoesNotExist as exc:
            raise ValidationError("Choose a same-tenant organization account.") from exc
        obj.account = account
        opportunity_ids = {
            opportunity.pk
            for opportunity in (form.cleaned_data.get("related_opportunities") or ())
        }
        opportunities = Opportunity.objects.select_for_update().filter(
            tenant=tenant,
            pk__in=opportunity_ids,
        )
        validate_account_plan_opportunities(tenant, account, opportunities)
        obj.save()
        form.save_m2m()
        action = "create" if locked is None else "update"
        write_audit_log(locked_user, obj, action, {"action": "account_plan"}, tenant=tenant)
    return obj


def account_plan_allowed_actions(plan, user=None):
    if user is not None and not can_manage_account_plan(plan, user):
        return {action: False for action in ("activate", "review_due", "complete", "archive")}
    return {
        "activate": plan.status == "draft",
        "review_due": plan.status == "active",
        "complete": plan.status in {"active", "review_due"},
        "archive": plan.status in {"draft", "active", "review_due", "completed"},
    }


def transition_account_plan(plan, tenant, user, target_status):
    from apps.accounts.models import User
    from apps.sales.models.ContactAccountManagement.AccountPlans import AccountPlan

    if not _same_tenant(plan, tenant):
        raise ValidationError("The account plan must belong to this workspace.")
    if not can_manage_account_plan(plan, user):
        raise ValidationError("Only the plan owner or a tenant administrator can change this plan.")
    with transaction.atomic():
        try:
            locked_user = User.objects.select_for_update().get(
                pk=user.pk,
                tenant=tenant,
                is_active=True,
            )
            locked = AccountPlan.objects.select_for_update().get(pk=plan.pk, tenant=tenant)
        except ObjectDoesNotExist as exc:
            raise ValidationError("The account plan or user is unavailable in this workspace.") from exc
        if not (
            _same_tenant(locked, getattr(locked_user, "tenant", None))
            and (_is_admin(locked_user) or locked.owner_id == locked_user.pk)
        ):
            raise ValidationError("Only the plan owner or a tenant administrator can change this plan.")
        allowed = {
            "active": {"draft"},
            "review_due": {"active"},
            "completed": {"active", "review_due"},
            "archived": {"draft", "active", "review_due", "completed"},
        }
        if target_status not in allowed or locked.status not in allowed[target_status]:
            raise ValidationError("That account-plan transition is not available.")
        locked.status = target_status
        locked.save(update_fields=["status", "updated_at"])
        write_audit_log(locked_user, locked, "update", {"action": "account_plan_transition", "status": target_status}, tenant=tenant)
    return locked
