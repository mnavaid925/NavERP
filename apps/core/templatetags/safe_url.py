"""Template helpers for safely rendering user-supplied URLs.

``safe_external_url`` returns a URL only when it uses the http/https scheme, else ``""``.
Django's template autoescaping HTML-encodes quotes/entities but does NOT neutralise a
``javascript:`` (or ``data:``) scheme in an ``href`` — so a stored hostile URL would execute
on click. ``URLField`` blocks those schemes at form-submit time, but a value written outside
form validation (admin raw edit, fixtures, a future API) would bypass that. Use this filter as
defense-in-depth wherever a user-supplied URL is rendered into an ``href``:

    {% load safe_url %}
    {% with link=obj.meeting_url|safe_external_url %}
      {% if link %}<a href="{{ link }}" rel="noopener noreferrer">Open</a>{% else %}{{ obj.meeting_url }}{% endif %}
    {% endwith %}
"""
from django import template

register = template.Library()

_SAFE_SCHEMES = ("http://", "https://")


@register.filter
def safe_external_url(value):
    """Return ``value`` if it is an http/https URL, otherwise ``""`` (so it never lands in an href)."""
    if value and str(value).strip().lower().startswith(_SAFE_SCHEMES):
        return value
    return ""
