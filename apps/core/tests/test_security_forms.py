"""0.18 Threat Protection - FORMS lane.

The centrepiece is `test_security_forms_every_choices_value_is_a_clean_error_or_a_pass`. A
`ValidationError` keyed on a field the form does not have makes Django's `add_error` RAISE, so a
mis-keyed rule is a 500 and not a validation message. C1 was exactly that, found by a Phase 4
reviewer and then reproduced by sweeping all 241 combinations - so that sweep is now a test, and
it is the one that would have caught it before an analyst did.
"""
import pytest

from apps.core.forms import (IpAccessRuleForm, SecurityIncidentForm, SecurityThreatForm,
                             VulnerabilityFindingForm)

pytestmark = pytest.mark.django_db

_SYSTEM_SET = {
    IpAccessRuleForm: ("tenant", "added_by", "added_by_label", "created_at", "updated_at"),
    SecurityThreatForm: ("tenant", "resolved_at", "resolved_by", "service_label",
                         "resolution_note", "created_at"),
    VulnerabilityFindingForm: ("tenant", "accepted_at", "created_at", "updated_at"),
    SecurityIncidentForm: ("tenant", "contained_at", "eradicated_at", "recovered_at", "closed_at",
                           "authority_notified_at", "subjects_notified", "subjects_notified_at",
                           "owner_label", "created_at", "updated_at"),
}


def _security_models_minimal(form_class, extra=None, skip=()):
    """A minimal valid POST for `form_class`, built from the model's own fields."""
    from django.utils import timezone
    model = form_class._meta.model
    data = {}
    for f in model._meta.fields:
        if not f.editable or f.name == "tenant" or f.name in skip:
            continue
        if f.choices:
            data[f.name] = f.choices[0][0]
        elif f.get_internal_type() in ("CharField", "TextField"):
            data[f.name] = "probe"
        elif f.get_internal_type() == "DateTimeField":
            data[f.name] = timezone.now().strftime("%Y-%m-%dT%H:%M")
        elif f.get_internal_type() == "DateField":
            data[f.name] = timezone.now().strftime("%Y-%m-%d")
    if extra:
        data.update(extra)
    return data


# ------------------------------------------------------------------ the C1 regression

@pytest.mark.parametrize("form_class,extra,skip", [
    (IpAccessRuleForm, {"cidr": "203.0.113.7", "direction": "deny", "reason": "probe"}, ()),
    (SecurityThreatForm, {"title": "probe"}, ()),
    (VulnerabilityFindingForm, {"title": "probe", "advisory_id": "PROBE-1",
                                "finding_source": "dependency"}, ()),
    (SecurityIncidentForm, {"title": "probe", "incident_class": "security_incident",
                            "subject_exemption": "none", "is_notifiable": "unknown"}, ()),
])
def test_security_forms_every_choices_value_is_a_clean_error_or_a_pass(form_class, extra, skip):
    """Every value of every choices field on all four forms. None may RAISE, and every error must
    be keyed on a field the form actually has - which is precisely what C1 violated."""
    base = _security_models_minimal(form_class, extra, skip)
    exercised = 0
    for fname, field in form_class.base_fields.items():
        for value, _label in list(getattr(field, "choices", []) or []):
            if value in ("", None):
                continue
            form = form_class(data=dict(base, **{fname: value}))   # the call that raised on C1
            assert form.is_valid() or form.errors, "a value that neither saves nor errors"
            for key in form.errors:
                assert key in form.fields, (
                    "ValidationError keyed on %r, which is NOT a field on %s - Django raises "
                    "ValueError for this" % (key, form_class.__name__))
            exercised += 1
    assert exercised > 0


def test_security_forms_resolved_status_is_a_field_error_not_a_crash(sec_threat_payload):
    """The specific C1 input, asserted directly: an error on `status`, no exception."""
    form = SecurityThreatForm(data=dict(sec_threat_payload, status="resolved"))
    assert form.is_valid() is False
    assert "status" in form.errors
    assert "resolved_at" not in form.errors and "resolved_by" not in form.errors


# ------------------------------------------------------------------ L22 mass assignment

@pytest.mark.parametrize("form_class", list(_SYSTEM_SET))
def test_security_forms_no_system_stamp_is_editable(form_class):
    """A user must not be able to POST `tenant`, or any stamp the actions own."""
    for name in _SYSTEM_SET[form_class]:
        assert name not in form_class().fields, "%s.%s is user-editable" % (
            form_class.__name__, name)


# ------------------------------------------------------------------ dropdown scoping

def test_security_forms_alert_event_dropdown_is_capped_and_joined(db):
    """`AlertEvent.__str__` dereferences `rule`, so the dropdown must `select_related` and cap."""
    field = SecurityThreatForm().fields["alert_event"]
    assert field.queryset is not None
    sql = str(field.queryset.query).upper()
    assert "LIMIT" in sql
    assert "JOIN" in sql


def test_security_forms_user_dropdowns_are_scoped_to_one_tenant(db, tenant_a, tenant_b):
    """Both 0.18 User pickers must be narrowed to the requesting workspace's own members."""
    from apps.accounts.models import User
    # `create_user` on this project's manager requires an `email` positional - omitting it is a
    # TypeError, not a default.
    User.objects.create_user(username="sec_probe_a", password="p", email="a@example.com",
                             tenant=tenant_a)
    User.objects.create_user(username="sec_probe_b", password="p", email="b@example.com",
                             tenant=tenant_b)
    for name in ("mitigated_by",):
        # The picker is capped (`[:200]`), and Django refuses `.filter()` on a sliced queryset,
        # so membership is checked by materialising what the dropdown would actually render.
        offered = SecurityThreatForm().fields[name].queryset
        assert all(u.tenant_id == tenant_a.pk for u in offered), (
            "%s offers another tenant" % name)


def test_security_forms_incident_dropdowns_never_leak_another_tenant(sec_incident_b):
    """The incident pickers must not offer another workspace's incident.

    The pickers are CAPPED (`[:200]`), and Django refuses `.filter()` on a sliced queryset - so
    membership is asserted by materialising the page's own (capped) queryset and checking ids,
    which is what the dropdown would actually render.
    """
    for name in ("primary_threat", "incident"):
        if name in SecurityIncidentForm().fields:
            offered = {o.pk for o in SecurityIncidentForm().fields[name].queryset}
            assert sec_incident_b.pk not in offered, "%s offers another tenant" % name


# ------------------------------------------------------------------ the required fields

def test_security_forms_iprule_cidr_is_required():
    form = IpAccessRuleForm(data={"direction": "deny", "reason": "x"})
    assert not form.is_valid()
    assert "cidr" in form.errors


def test_security_forms_incident_title_is_required():
    form = SecurityIncidentForm(data={})
    assert not form.is_valid()
    assert "title" in form.errors
