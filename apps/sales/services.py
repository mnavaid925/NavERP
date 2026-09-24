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
